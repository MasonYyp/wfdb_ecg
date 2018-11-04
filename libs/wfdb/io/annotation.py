import copy
import numpy as np
import os
import pandas as pd
import re

from . import download
from . import _header
from . import record


class Annotation(object):
    """
    The class representing WFDB annotations.

    Annotation objects can be created using the initializer, or by reading a
    WFDB annotation file with `rdann`.

    The attributes of the Annotation object give information about the
    annotation as specified by:
    https://www.physionet.org/physiotools/wag/annot-5.htm

    Call `show_ann_labels()` to see the list of standard annotation codes. Any
    text used to label annotations that are not one of these codes should go in
    the 'aux_note' field rather than the 'sym' field.

    Examples
    --------
    >>> ann1 = wfdb.Annotation(record_name='rec1', extension='atr',
                               sample=[10,20,400], symbol=['N','N','['],
                               aux_note=[None, None, 'Serious Vfib'])

    """

    def __init__(self, record_name, extension, sample, symbol=None,
                 subtype=None, chan=None, num=None, aux_note=None, fs=None,
                 label_store=None, description=None, custom_labels=None,
                 contained_labels=None):
        """
        Parameters
        ----------
        record_name : str
            The base file name (without extension) of the record that the
            annotation is associated with.
        extension : str
            The file extension of the file the annotation is stored in.
        sample : numpy array
            A numpy array containing the annotation locations in samples relative to
            the beginning of the record.
        symbol : list, or numpy array, optional
            The symbols used to display the annotation labels. List or numpy array.
            If this field is present, `label_store` must not be present.
        subtype : numpy array, optional
            A numpy array containing the marked class/category of each annotation.
        chan : numpy array, optional
            A numpy array containing the signal channel associated with each
            annotation.
        num : numpy array, optional
            A numpy array containing the labelled annotation number for each
            annotation.
        aux_note : list, optional
            A list containing the auxiliary information string (or None for
            annotations without notes) for each annotation.
        fs : int, or float, optional
            The sampling frequency of the record.
        label_store : numpy array, optional
            The integer value used to store/encode each annotation label
        description : list, optional
            A list containing the descriptive string of each annotation label.
        custom_labels : pandas dataframe, optional
            The custom annotation labels defined in the annotation file. Maps
            the relationship between the three label fields. The data type is a
            pandas DataFrame with three columns:
            ['label_store', 'symbol', 'description']
        contained_labels : pandas dataframe, optional
            The unique labels contained in this annotation. Same structure as
            `custom_labels`.

        """
        self.record_name = record_name
        self.extension = extension

        self.sample = sample
        self.symbol = symbol

        self.subtype = subtype
        self.chan = chan
        self.num = num
        self.aux_note = aux_note
        self.fs = fs

        self.label_store = label_store
        self.description = description

        self.custom_labels = custom_labels
        self.contained_labels = contained_labels

        self.ann_len = len(self.sample)

        #__label_map__: (storevalue, symbol, description) hidden attribute

    # Equal comparison operator for objects of this type
    def __eq__(self, other):
        att1 = self.__dict__
        att2 = other.__dict__

        if set(att1.keys()) != set(att2.keys()):
            print('keyset')
            return False

        for k in att1.keys():
            v1 = att1[k]
            v2 = att2[k]

            if type(v1) != type(v2):
                print(k)
                return False

            if isinstance(v1, np.ndarray):
                if not np.array_equal(v1, v2):
                    print(k)
                    return False
            elif isinstance(v1, pd.DataFrame):
                if not v1.equals(v2):
                    print(k)
                    return False
            else:
                if v1 != v2:
                    print(k)
                    return False

        return True

    def apply_range(self, sampfrom=0, sampto=None):
        """
        Filter the annotation attributes to keep only items between the
        desired sample values

        """
        sampto = sampto or self.sample[-1]

        kept_inds = np.intersect1d(np.where(self.sample>=sampfrom),
                                   np.where(self.sample<=sampto))


        for field in ['sample', 'label_store', 'subtype', 'chan', 'num']:
            setattr(self, field, getattr(self, field)[kept_inds])

        self.aux_note = [self.aux_note[i] for i in kept_inds]

        self.ann_len = len(self.sample)

    def wrann(self, write_fs=False, write_dir=''):
        """
        Write a WFDB annotation file from this object.

        Parameters
        ----------
        write_fs : bool, optional
            Whether to write the `fs` attribute to the file.

        """
        for field in ['record_name', 'extension']:
            if getattr(self, field) is None:
                raise Exception('Missing required field for writing annotation file: ',field)

        present_label_fields = self.get_label_fields()
        if not present_label_fields:
            raise Exception('At least one annotation label field is required to write the annotation: ', ann_label_fields)

        # Check the validity of individual fields
        self.check_fields()

        # Standardize the format of the custom_labels field
        self.standardize_custom_labels()

        # Create the label map used in this annotaion
        self.create_label_map()

        # Check the cohesion of fields
        self.check_field_cohesion(present_label_fields)

        # Calculate the label_store field if necessary
        if 'label_store' not in present_label_fields:
            self.convert_label_attribute(source_field=present_label_fields[0],
                                         target_field='label_store')

        # Write the header file using the specified fields
        self.wr_ann_file(write_fs=write_fs, write_dir=write_dir)

        return

    def get_label_fields(self):
        """
        Get the present label fields in the object
        """
        present_label_fields = []
        for field in ann_label_fields:
            if getattr(self, field) is not None:
                present_label_fields.append(field)

        return present_label_fields

    # Check the set fields of the annotation object
    def check_fields(self):
        # Check all set fields
        for field in ALLOWED_TYPES:
            if getattr(self, field) is not None:
                # Check the type of the field's elements
                self.check_field(field)
        return



    def check_field(self, field):
        """
        Check a particular annotation field
        """

        item = getattr(self, field)

        if not isinstance(item, ALLOWED_TYPES[field]):
            raise TypeError('The '+field+' field must be one of the following types:', ALLOWED_TYPES[field])

        # Numerical integer annotation fields: sample, label_store, sub,
        # chan, num
        if ALLOWED_TYPES[field] == (np.ndarray):
            record.check_np_array(item=item, field_name=field, ndim=1,
                                  parent_class=np.integer, channel_num=None)

        # Field specific checks
        if field == 'record_name':
            if bool(re.search('[^-\w]', self.record_name)):
                raise ValueError('record_name must only comprise of letters, digits, hyphens, and underscores.')
        elif field == 'extension':
            if bool(re.search('[^a-zA-Z]', self.extension)):
                raise ValueError('extension must only comprise of letters.')
        elif field == 'fs':
            if self.fs <=0:
                raise ValueError('The fs field must be a non-negative number')
        elif field == 'custom_labels':
            """
            The role of this section is just to check the
            elements of this item, without utilizing
            any other fields. No format conversion
            or free value looksups etc are done.
            """

            # Check the structure of the subelements
            if isinstance(item, pd.DataFrame):
                column_names = list(item)
                if 'symbol' in column_names and 'description' in column_names:
                    if 'label_store' in column_names:
                        label_store = list(item['label_store'].values)
                    else:
                        label_store = None
                    symbol = item['symbol'].values
                    description = item['description'].values
                else:
                    raise ValueError(''.join(['If the '+field+' field is pandas dataframe, its columns',
                                             ' must be one of the following:\n-[label_store, symbol, description]',
                                             '\n-[symbol, description]']))
            else:
                if set([len(i) for i in item]) == {2}:
                    label_store = None
                    symbol = [i[0] for i in item]
                    description = [i[1] for i in item]
                elif set([len(i) for i in item]) == {3}:
                    label_store = [i[0] for i in item]
                    symbol = [i[1] for i in item]
                    description = [i[2] for i in item]
                else:
                    raise ValueError(''.join(['If the '+field+' field is an array-like object, its subelements',
                                             ' must be one of the following:\n- tuple triplets storing: ',
                                             '(label_store, symbol, description)\n- tuple pairs storing: ',
                                             '(symbol, description)']))

            # Check the values of the subelements
            if label_store:
                if len(item) != len(set(label_store)):
                    raise ValueError('The label_store values of the '+field+' field must be unique')

                if min(label_store) < 1 or max(label_store) > 49:
                    raise ValueError('The label_store values of the custom_labels field must be between 1 and 49')

            if len(item) != len(set(symbol)):
                raise ValueError('The symbol values of the '+field+' field must be unique')

            for i in range(len(item)):
                if label_store:
                    if not hasattr(label_store[i], '__index__'):
                        raise TypeError('The label_store values of the '+field+' field must be integer-like')

                if not isinstance(symbol[i], str_types) or len(symbol[i]) not in [1,2,3]:
                    raise ValueError('The symbol values of the '+field+' field must be strings of length 1 to 3')

                if bool(re.search('[ \t\n\r\f\v]', symbol[i])):
                    raise ValueError('The symbol values of the '+field+' field must not contain whitespace characters')

                if not isinstance(description[i], str_types):
                    raise TypeError('The description values of the '+field+' field must be strings')

                # Would be good to enfore this but existing garbage annotations have tabs and newlines...
                #if bool(re.search('[\t\n\r\f\v]', description[i])):
                #    raise ValueError('The description values of the '+field+' field must not contain tabs or newlines')

        # The string fields
        elif field in ['symbol', 'description', 'aux_note']:
            uniq_elements = set(item)

            for e in uniq_elements:
                if not isinstance(e, str_types):
                    raise TypeError('Subelements of the '+field+' field must be strings')

            if field == 'symbol':
                for e in uniq_elements:
                    if len(e) not in [1,2,3]:
                        raise ValueError('Subelements of the '+field+' field must be strings of length 1 to 3')
                    if bool(re.search('[ \t\n\r\f\v]', e)):
                        raise ValueError('Subelements of the '+field+' field may not contain whitespace characters')
            else:
                for e in uniq_elements:
                    if bool(re.search('[\t\n\r\f\v]', e)):
                        raise ValueError('Subelements of the '+field+' field must not contain tabs or newlines')

        elif field == 'sample':
            if len(self.sample) == 1:
                sampdiffs = np.array([self.sample[0]])
            elif len(self.sample) > 1:
                sampdiffs = np.concatenate(([self.sample[0]], np.diff(self.sample)))
            else:
                raise ValueError("The 'sample' field must be a numpy array with length greater than 0")
            if min(self.sample) < 0 :
                raise ValueError("The 'sample' field must only contain non-negative integers")
            if min(sampdiffs) < 0 :
                raise ValueError("The 'sample' field must contain monotonically increasing sample numbers")
            if max(sampdiffs) > 2147483648:
                raise ValueError('WFDB annotation files cannot store sample differences greater than 2**31')

        elif field == 'label_store':
            if min(item) < 1 or max(item) > 49:
                raise ValueError('The label_store values must be between 1 and 49')

        # The C WFDB library stores num/sub/chan as chars.
        elif field == 'subtype':
            # signed character
            if min(self.subtype) < 0 or max(self.subtype) >127:
                raise ValueError("The 'subtype' field must only contain non-negative integers up to 127")
        elif field == 'chan':
            # un_signed character
            if min(self.chan) < 0 or max(self.chan) >255:
                raise ValueError("The 'chan' field must only contain non-negative integers up to 255")
        elif field == 'num':
            # signed character
            if min(self.num) < 0 or max(self.num) >127:
                raise ValueError("The 'num' field must only contain non-negative integers up to 127")

        return


    def check_field_cohesion(self, present_label_fields):
        """
        Check that the content and structure of different fields are consistent
        with one another.
        """
        # Ensure all written annotation fields have the same length
        nannots = len(self.sample)

        for field in ['sample', 'num', 'subtype', 'chan', 'aux_note']+present_label_fields:
            if getattr(self, field) is not None:
                if len(getattr(self, field)) != nannots:
                    raise ValueError("The lengths of the 'sample' and '"+field+"' fields do not match")

        # Ensure all label fields are defined by the label map. This has to be checked because
        # it is possible the user defined (or lack of) custom_labels does not capture all the
        # labels present.
        for field in present_label_fields:
            defined_values = self.__label_map__[field].values

            if set(getattr(self, field)) - set(defined_values) != set():
                raise ValueError('\n'.join(['\nThe '+field+' field contains elements not encoded in the stardard WFDB annotation labels, or this object\'s custom_labels field',
                                      '- To see the standard WFDB annotation labels, call: show_ann_labels()',
                                      '- To transfer non-encoded symbol items into the aux_note field, call: self.sym_to_aux()',
                                      '- To define custom labels, set the custom_labels field as a list of tuple triplets with format: (label_store, symbol, description)']))

        return


    def standardize_custom_labels(self):
        """
        Set the custom_labels field of the object to a standardized format:
        3 column pandas df with ann_label_fields as columns.

        Does nothing if there are no custom labels defined.
        Does nothing if custom_labels is already a df with all 3 columns

        If custom_labels is an iterable of pairs/triplets, this
        function will convert it into a df.

        If the label_store attribute is not already defined, this
        function will automatically choose values by trying to use:
        1. The undefined store values from the standard wfdb annotation
           label map.
        2. The unused label store values. This is extracted by finding the
           set of all labels contained in this annotation object and seeing
           which symbols/descriptions are not used.

        If there are more custom labels defined than there are enough spaces,
        even in condition 2 from above, this function will raise an error.

        This function must work when called as a standalone.
        """
        custom_labels = self.custom_labels

        if custom_labels is None:
            return

        self.check_field('custom_labels')

        # Convert to dataframe if not already
        if not isinstance(custom_labels, pd.DataFrame):
            if len(self.custom_labels[0]) == 2:
                symbol = self.get_custom_label_attribute('symbol')
                description = self.get_custom_label_attribute('description')
                custom_labels = pd.DataFrame({'symbol': symbol, 'description': description})
            else:
                label_store = self.get_custom_label_attribute('label_store')
                symbol = self.get_custom_label_attribute('symbol')
                description = self.get_custom_label_attribute('description')
                custom_labels = pd.DataFrame({'label_store':label_store, 'symbol': symbol, 'description': description})

        # Assign label_store values to the custom labels if not defined
        if 'label_store' not in list(custom_labels):
            undefined_label_stores = self.get_undefined_label_stores()

            if len(custom_labels) > len(undefined_label_stores):
                available_label_stores = self.get_available_label_stores()
            else:
                available_label_stores = undefined_label_stores

            n_custom_labels = custom_labels.shape[0]

            if n_custom_labels > len(available_label_stores):
                raise ValueError('There are more custom_label definitions than storage values available for them.')

            custom_labels['label_store'] = available_label_stores[:n_custom_labels]

        custom_labels.set_index(custom_labels['label_store'].values, inplace=True)
        custom_labels = custom_labels[list(ann_label_fields)]

        self.custom_labels = custom_labels

        return

    def get_undefined_label_stores(self):
        """
        Get the label_store values not defined in the
        standard wfdb annotation labels.
        """
        return list(set(range(50)) - set(ann_label_table['label_store']))


    def get_available_label_stores(self, usefield='tryall'):
        """
        Get the label store values that may be used
        for writing this annotation.

        Available store values include:
        - the undefined values in the standard wfdb labels
        - the store values not used in the current
          annotation object.
        - the store values whose standard wfdb symbols/descriptions
          match those of the custom labels (if custom_labels exists)

        If 'usefield' is explicitly specified, the function will use that
        field to figure out available label stores. If 'usefield'
        is set to 'tryall', the function will choose one of the contained
        attributes by checking availability in the order: label_store, symbol, description
        """


        # Figure out which field to use to get available labels stores.
        if usefield == 'tryall':
            if self.label_store is not None:
                usefield = 'label_store'
            elif self.symbol is not None:
                usefield = 'symbol'
            elif self.description is not None:
                usefield = 'description'
            else:
                raise ValueError('No label fields are defined. At least one of the following is required: ', ann_label_fields)
            return self.get_available_label_stores(usefield = usefield)
        # Use the explicitly stated field to get available stores.
        else:
            # If usefield == 'label_store', there are slightly fewer/different steps
            # compared to if it were another option

            contained_field = getattr(self, usefield)

            # Get the unused label_store values
            if usefield == 'label_store':
                unused_label_stores = set(ann_label_table['label_store'].values) - contained_field
            else:
                # the label_store values from the standard wfdb annotation labels
                # whose symbols are not contained in this annotation
                unused_field = set(ann_label_table[usefield].values) - contained_field
                unused_label_stores = ann_label_table.loc[ann_label_table[usefield] in unused_field, 'label_store'].values

            # Get the standard wfdb label_store values overwritten by the
            # custom_labels if any
            if self.custom_symbols is not None:
                custom_field = set(self.get_custom_label_attribute(usefield))
                if usefield == 'label_store':
                    overwritten_label_stores = set(custom_field).intersection(set(ann_label_table['label_store']))
                else:
                    overwritten_fields = set(custom_field).intersection(set(ann_label_table[usefield]))
                    overwritten_label_stores = ann_label_table.loc[ann_label_table[usefield] in overwritten_fields, 'label_store'].values
            else:
                overwritten_label_stores = set()


            # The undefined values in the standard wfdb labels
            undefined_label_stores = self.get_undefined_label_stores()
            # Final available label stores = undefined + unused + overwritten
            available_label_stores = set(undefined_label_stores).union(set(unused_label_stores)).union(overwritten_label_stores)

            return available_label_stores


    def get_custom_label_attribute(self, attribute):
        """
        Get a list of the custom_labels attribute.
        ie. label_store, symbol, or description.

        The custom_labels variable could be in
        a number of formats
        """

        if attribute not in ann_label_fields:
            raise ValueError('Invalid attribute specified')

        if isinstance(self.custom_labels, pd.DataFrame):
            if 'label_store' not in list(self.custom_labels):
                raise ValueError('label_store not defined in custom_labels')
            a = list(self.custom_labels[attribute].values)
        else:
            if len(self.custom_labels[0]) == 2:
                if attribute == 'label_store':
                    raise ValueError('label_store not defined in custom_labels')
                elif attribute == 'symbol':
                    a = [l[0] for l in self.custom_labels]
                elif attribute == 'description':
                    a = [l[1] for l in self.custom_labels]
            else:
                if attribute == 'label_store':
                    a = [l[0] for l in self.custom_labels]
                elif attribute == 'symbol':
                    a = [l[1] for l in self.custom_labels]
                elif attribute == 'description':
                    a = [l[2] for l in self.custom_labels]

        return a


    def create_label_map(self, inplace=True):
        """
        Creates mapping df based on ann_label_table and self.custom_labels.

        Table composed of entire WFDB standard annotation table, overwritten/appended
        with custom_labels if any. Sets __label_map__ attribute, or returns value.
        """

        label_map =  ann_label_table.copy()

        if self.custom_labels is not None:
            self.standardize_custom_labels()
            for i in self.custom_labels.index:
                label_map.loc[i] = self.custom_labels.loc[i]

        if inplace:
            self.__label_map__ = label_map
        else:
            return label_map


    def wr_ann_file(self, write_fs, write_dir=''):
        """
        Calculate the bytes used to encode an annotation set and
        write them to an annotation file
        """

        # Calculate the fs bytes to write if present and desired to write
        if write_fs:
            fs_bytes = self.calc_fs_bytes()
        else:
            fs_bytes = []
        # Calculate the custom_labels bytes to write if present
        cl_bytes = self.calc_cl_bytes()
        # Calculate the core field bytes to write
        core_bytes = self.calc_core_bytes()

        # Mark the end of the special annotation types if needed
        if fs_bytes == [] and cl_bytes == []:
            end_special_bytes = []
        else:
            end_special_bytes = [0, 236, 255, 255, 255, 255, 1, 0]

        # Write the file
        with open(os.path.join(write_dir, self.record_name+'.'+self.extension),
                  'wb') as f:
            # Combine all bytes to write: fs (if any), custom annotations (if any), main content, file terminator
            np.concatenate((fs_bytes, cl_bytes, end_special_bytes, core_bytes,
                            np.array([0,0]))).astype('u1').tofile(f)

        return

    # Calculate the bytes written to the annotation file for the fs field
    def calc_fs_bytes(self):

        if self.fs is None:
            return []

        # Initial indicators of encoding fs
        data_bytes = [0, 88, 0, 252, 35, 35, 32, 116, 105, 109, 101, 32, 114,
                      101, 115, 111, 108, 117, 116, 105, 111, 110, 58, 32]

        # Check if fs is close enough to int
        if isinstance(self.fs, float):
            if round(self.fs,8) == float(int(self.fs)):
                self.fs = int(self.fs)

        fschars = str(self.fs)
        ndigits = len(fschars)

        for i in range(ndigits):
            data_bytes.append(ord(fschars[i]))

        # Fill in the aux_note length
        data_bytes[2] = ndigits + 20

        # odd number of digits
        if ndigits % 2:
            data_bytes.append(0)

        return np.array(data_bytes).astype('u1')

    # Calculate the bytes written to the annotation file for the
    # custom_labels field
    def calc_cl_bytes(self):

        if self.custom_labels is None:
            return []

        # The start wrapper: '0 NOTE length aux_note ## annotation type definitions'
        headbytes = [0,88,30,252,35,35,32,97,110,110,111,116,97,116,105,111,110,32,116,
                     121,112,101,32,100,101,102,105,110,105,116,105,111,110,115]

        # The end wrapper: '0 NOTE length aux_note ## end of definitions' followed by SKIP -1, +1
        tailbytes =  [0,88,21,252,35,35,32,101,110,100,32,111,102,32,100,101,102,105,110,
                      105,116,105,111,110,115,0]

        custom_bytes = []

        for i in self.custom_labels.index:
            custom_bytes += custom_triplet_bytes(list(self.custom_labels.loc[i, list(ann_label_fields)]))

        # writecontent = []
        # for i in range(len(self.custom_labels)):
        #     writecontent.append([freenumbers[i],list(custom_labels.keys())[i],list(custom_labels.values())[i]])

        # custombytes = [customcode2bytes(triplet) for triplet in writecontent]
        # custombytes = [item for sublist in custombytes for item in sublist]

        return np.array(headbytes+custom_bytes+tailbytes).astype('u1')

    def calc_core_bytes(self):
        """
        Convert all used annotation fields into bytes to write
        """
        # The difference sample to write
        if len(self.sample) == 1:
            sampdiff = np.array([self.sample[0]])
        else:
            sampdiff = np.concatenate(([self.sample[0]], np.diff(self.sample)))

        # Create a copy of the annotation object with a
        # compact version of fields to write
        compact_annotation = copy.deepcopy(self)
        compact_annotation.compact_fields()


        # The optional fields to be written. Write if they are not None or all empty
        extra_write_fields = []

        for field in ['num', 'subtype', 'chan', 'aux_note']:
            if not isblank(getattr(compact_annotation, field)):
                extra_write_fields.append(field)

        data_bytes = []

        # Iterate across all fields one index at a time
        for i in range(len(sampdiff)):

            # Process the samp (difference) and sym items
            data_bytes.append(field2bytes('samptype', [sampdiff[i], self.symbol[i]]))

            # Process the extra optional fields
            for field in extra_write_fields:
                value = getattr(compact_annotation, field)[i]
                if value is not None:
                    data_bytes.append(field2bytes(field, value))

        # Flatten and convert to correct format
        data_bytes = np.array([item for sublist in data_bytes for item in sublist]).astype('u1')

        return data_bytes

    # Compact all of the object's fields so that the output
    # writing annotation file writes as few bytes as possible
    def compact_fields(self):

        # Number of annotations
        nannots = len(self.sample)

        # Chan and num carry over previous fields. Get lists of as few
        # elements to write as possible
        self.chan = compact_carry_field(self.chan)
        self.num = compact_carry_field(self.num)

        # Elements of 0 (default) do not need to be written for subtype.
        # num and sub are signed in original c package...
        if self.subtype is not None:
            if isinstance(self.subtype, list):
                for i in range(nannots):
                    if self.subtype[i] == 0:
                        self.subtype[i] = None
                if np.array_equal(self.subtype, [None]*nannots):
                    self.subtype = None
            else:
                zero_inds = np.where(self.subtype==0)[0]
                if len(zero_inds) == nannots:
                    self.subtype = None
                else:
                    self.subtype = list(self.subtype)
                    for i in zero_inds:
                        self.subtype[i] = None

        # Empty aux_note strings are not written
        if self.aux_note is not None:
            for i in range(nannots):
                if self.aux_note[i] == '':
                    self.aux_note[i] = None
            if np.array_equal(self.aux_note, [None]*nannots):
                self.aux_note = None


    def sym_to_aux(self):
        # Move non-encoded symbol elements into the aux_note field
        self.check_field('symbol')

        # Non-encoded symbols
        label_table_map = self.create_label_map(inplace=False)
        external_syms = set(self.symbol) - set(label_table_map['symbol'].values)

        if external_syms == set():
            return

        if self.aux_note is None:
            self.aux_note = ['']*len(self.sample)

        for ext in external_syms:
            for i in [i for i,x in enumerate(self.symbol) if x == ext]:
                if not self.aux_note[i]:
                    self.aux_note[i] = self.symbol[i]
                else:
                    self.aux_note[i] = self.symbol[i]+' '+self.aux_note[i]
                self.symbol[i] = '"'
        return


    def get_contained_labels(self, inplace=True):
        """
        Get the set of unique labels contained in this annotation.
        Returns a pandas dataframe or sets the __contained__ labels
        attribute of the object.


        Requires the label_store field to be set.

        Function will try to use attributes contained in the order:
        1. label_store
        2. symbol
        3. description

        This function should also be called
        to summarize information about an
        annotation after it has been
        read. Should not be a helper function
        to others except rdann.
        """
        if self.custom_labels is not None:
            self.check_field('custom_labels')

        # Create the label map
        label_map = ann_label_table.copy()

        # Convert the tuple triplets into a pandas dataframe if needed
        if isinstance(self.custom_labels, (list, tuple)):
            custom_labels = label_triplets_to_df(self.custom_labels)
        elif isinstance(self.custom_labels, pd.DataFrame):
            # Set the index just in case it doesn't already match the label_store
            self.custom_labels.set_index(
                self.custom_labels['label_store'].values, inplace=True)
            custom_labels = self.custom_labels
        else:
            custom_labels = None

        # Merge the standard wfdb labels with the custom labels.
        # custom labels values overwrite standard wfdb if overlap.
        if custom_labels is not None:
            for i in custom_labels.index:
                label_map.loc[i] = custom_labels.loc[i]
            # This doesn't work...
            # label_map.loc[custom_labels.index] = custom_labels.loc[custom_labels.index]

        # Get the labels using one of the features
        if self.label_store is not None:
            index_vals = set(self.label_store)
            reset_index = False
        elif self.symbol is not None:
            index_vals = set(self.symbol)
            label_map.set_index(label_map['symbol'].values, inplace=True)
            reset_index = True
        elif self.description is not None:
            index_vals = set(self.description)
            label_map.set_index(label_map['description'].values, inplace=True)
            reset_index = True
        else:
            raise Exception('No annotation labels contained in object')

        contained_labels = label_map.loc[index_vals, :]

        if reset_index:
            contained_labels.set_index(contained_labels['label_store'].values,
                                       inplace=True)

        if inplace:
            self.contained_labels = contained_labels
            return
        else:
            return contained_labels

    def set_label_elements(self, wanted_label_elements):
        """
        Set one or more label elements based on
        at least one of the others
        """
        if isinstance(wanted_label_elements, str):
            wanted_label_elements = [wanted_label_elements]

        # Figure out which desired label elements are missing
        missing_elements = [e for e in wanted_label_elements if getattr(self, e) is None]

        contained_elements = [e for e in ann_label_fields if getattr(self, e )is not None]

        if not contained_elements:
            raise Exception('No annotation labels contained in object')

        for e in missing_elements:
            self.convert_label_attribute(contained_elements[0], e)

        unwanted_label_elements = list(set(ann_label_fields)
                                       - set(wanted_label_elements))

        self.rm_attributes(unwanted_label_elements)

        return

    def rm_attributes(self, attributes):
        if isinstance(attributes, str):
            attributes = [attributes]
        for a in attributes:
            setattr(self, a, None)
        return

    def convert_label_attribute(self, source_field, target_field, inplace=True,
                                overwrite=True):
        """
        Convert one label attribute (label_store, symbol, or description) to another.
        Input arguments:
        - inplace - If True, sets the object attribute. If False, returns the value.
        - overwrite - if True, performs conversion and replaces target field attribute even if the
          target attribute already has a value. If False, does not perform conversion in the aforementioned case.
          Set to True (do conversion) if inplace=False.

        Creates mapping df on the fly based on ann_label_table and self.custom_labels
        """
        if inplace and not overwrite:
            if getattr(self, target_field) is not None:
                return

        label_map = self.create_label_map(inplace=False)
        label_map.set_index(label_map[source_field].values, inplace=True)

        target_item = label_map.loc[getattr(self, source_field), target_field].values

        if target_field != 'label_store':
            # Should already be int64 dtype if target is label_store
            target_item = list(target_item)

        if inplace:
            setattr(self, target_field, target_item)
        else:
            return target_item


def label_triplets_to_df(triplets):
    """
    Get a pd dataframe from a tuple triplets
    used to define annotation labels.

    The triplets should come in the
    form: (label_store, symbol, description)
    """

    label_df = pd.DataFrame({'label_store':np.array([t[0] for t in triplets],
                                                    dtype='int'),
                             'symbol':[t[1] for t in triplets],
                             'description':[t[2] for t in triplets]})

    label_df.set_index(label_df['label_store'].values, inplace=True)
    label_df = label_df[list(ann_label_fields)]

    return label_df


def custom_triplet_bytes(custom_triplet):
    """
    Convert triplet of [label_store, symbol, description] into bytes
    for defining custom labels in the annotation file
    """
    # Structure: 0, NOTE, len(aux_note), aux_note, codenumber, space, codesymbol, space, description, (0 null if necessary)
    # Remember, aux_note string includes 'number(s)<space><symbol><space><description>''
    annbytes = [0, 88, len(custom_triplet[2]) + 3 + len(str(custom_triplet[0])), 252] + [ord(c) for c in str(custom_triplet[0])] \
               + [32] + [ord(custom_triplet[1])] + [32] + [ord(c) for c in custom_triplet[2]]

    if len(annbytes) % 2:
        annbytes.append(0)

    return annbytes


# Tests whether the item is blank
def isblank(x):
    if x is None:
        return True
    elif isinstance(x, list):
        if set(x) == set([None]):
            return True
    return False


def compact_carry_field(full_field):
    """
    Return the compact list version of a list/array of an
    annotation field that has previous values carried over
    (chan or num)
    - The first sample is 0 by default. Only set otherwise
      if necessary.
    - Only set fields if they are different from their prev
      field
    """

    # Keep in mind that the field may already be compact or None

    if full_field is None:
        return None

    # List of same length. Place None where element
    # does not need to be written
    compact_field = [None]*len(full_field)

    prev_field = 0

    for i in range(len(full_field)):
        current_field = full_field[i]
        if current_field != prev_field:
            compact_field[i] = current_field
            prev_field = current_field

    # May further simplify
    if np.array_equal(compact_field, [None]*len(full_field)):
        compact_field = None

    return compact_field


# Convert an annotation field into bytes to write
def field2bytes(field, value):

    data_bytes = []

    # samp and sym bytes come together
    if field == 'samptype':
        # Numerical value encoding annotation symbol
        typecode = ann_label_table.loc[ann_label_table['symbol']==value[1], 'label_store'].values[0]

        # sample difference
        sd = value[0]

        # Add SKIP element if value is too large for single byte
        if sd>1023:
            # 8 bytes in total:
            # - [0, 59>>2] indicates SKIP
            # - Next 4 gives sample difference
            # - Final 2 give 0 and sym
            data_bytes = [0, 236, (sd&16711680)>>16, (sd&4278190080)>>24, sd&255, (sd&65280)>>8, 0, 4*typecode]
        # Just need samp and sym
        else:
            # - First byte stores low 8 bits of samp
            # - Second byte stores high 2 bits of samp
            #   and sym
            data_bytes = [sd & 255, ((sd & 768) >> 8) + 4*typecode]

    elif field == 'num':
        # First byte stores num
        # second byte stores 60*4 indicator
        data_bytes = [value, 240]
    elif field == 'subtype':
        # First byte stores subtype
        # second byte stores 61*4 indicator
        data_bytes = [value, 244]
    elif field == 'chan':
        # First byte stores num
        # second byte stores 62*4 indicator
        data_bytes = [value, 248]
    elif field == 'aux_note':
        # - First byte stores length of aux_note field
        # - Second byte stores 63*4 indicator
        # - Then store the aux_note string characters
        data_bytes = [len(value), 252] + [ord(i) for i in value]
        # Zero pad odd length aux_note strings
        if len(value) % 2:
            data_bytes.append(0)

    return data_bytes


def wrann(record_name, extension, sample, symbol=None, subtype=None, chan=None,
          num=None, aux_note=None, label_store=None, fs=None,
          custom_labels=None, write_dir=''):
    """
    Write a WFDB annotation file.

    Specify at least the following:

    - The record name of the WFDB record (record_name)
    - The annotation file extension (extension)
    - The annotation locations in samples relative to the beginning of
      the record (sample)
    - Either the numerical values used to store the labels
      (`label_store`), or more commonly, the display symbols of each
      label (`symbol`).

    Parameters
    ----------
    record_name : str
        The string name of the WFDB record to be written (without any file
        extensions).
    extension : str
        The string annotation file extension.
    sample : numpy array
        A numpy array containing the annotation locations in samples relative to
        the beginning of the record.
    symbol : list, or numpy array, optional
        The symbols used to display the annotation labels. List or numpy array.
        If this field is present, `label_store` must not be present.
    subtype : numpy array, optional
        A numpy array containing the marked class/category of each annotation.
    chan : numpy array, optional
        A numpy array containing the signal channel associated with each
        annotation.
    num : numpy array, optional
        A numpy array containing the labelled annotation number for each
        annotation.
    aux_note : list, optional
        A list containing the auxiliary information string (or None for
        annotations without notes) for each annotation.
    label_store : numpy array, optional
        A numpy array containing the integer values used to store the
        annotation labels. If this field is present, `symbol` must not be
        present.
    fs : int, or float, optional
        The numerical sampling frequency of the record to be written to the file.
    custom_labels : pandas dataframe, optional
        The map of custom defined annotation labels used for this annotation, in
        addition to the standard WFDB annotation labels. Custom labels are
        defined by two or three fields:

        - The integer values used to store custom annotation labels in the file
          (optional)
        - Their short display symbols
        - Their long descriptions.

        This input argument may come in four formats:

        1. A pandas.DataFrame object with columns:
           ['label_store', 'symbol', 'description']
        2. A pandas.DataFrame object with columns: ['symbol', 'description']
           If this option is chosen, label_store values are automatically chosen.
        3. A list or tuple of tuple triplets, with triplet elements
           representing: (label_store, symbol, description).
        4. A list or tuple of tuple pairs, with pair elements representing:
           (symbol, description). If this option is chosen, label_store values
           are automatically chosen.

        If the `label_store` field is given for this function, and
        `custom_labels` is defined, `custom_labels` must contain `label_store`
        in its mapping. ie. it must come in format 1 or 3 above.
    write_dir : str, optional
        The directory in which to write the annotation file

    Notes
    -----
    This is a gateway function, written as a simple way to write WFDB annotation
    files without needing to explicity create an Annotation object. You may also
    create an Annotation object, manually set its attributes, and call its
    `wrann` instance method.

    Each annotation stored in a WFDB annotation file contains a sample field and
    a label field. All other fields may or may not be present.

    Examples
    --------
    >>> # Read an annotation as an Annotation object
    >>> annotation = wfdb.rdann('b001', 'atr', pb_dir='cebsdb')
    >>> # Write a copy of the annotation file
    >>> wfdb.wrann('b001', 'cpy', annotation.sample, annotation.symbol)

    """

    # Create Annotation object
    annotation = Annotation(record_name=record_name, extension=extension,
                            sample=sample, symbol=symbol, subtype=subtype,
                            chan=chan, num=num, aux_note=aux_note,
                            label_store=label_store, fs=fs,
                            custom_labels=custom_labels)

    # Find out which input field describes the labels
    if symbol is None:
        if label_store is None:
            raise Exception("Either the 'symbol' field or the 'label_store' field must be set")
    else:
        if label_store is None:
            annotation.sym_to_aux()
        else:
            raise Exception("Only one of the 'symbol' and 'label_store' fields may be input, for describing annotation labels")

    # Perform field checks and write the annotation file
    annotation.wrann(write_fs=True, write_dir=write_dir)


def show_ann_labels():
    """
    Display the standard wfdb annotation label mapping.

    Examples
    --------
    >>> show_ann_labels()

    """
    print(ann_label_table)


def show_ann_classes():
    """
    Display the standard wfdb annotation classes

    Examples
    --------
    >>> show_ann_classes()

    """
    print(ann_class_table)


# todo: return as df option?
def rdann(record_name, extension, sampfrom=0, sampto=None, shift_samps=False,
          pb_dir=None, return_label_elements=['symbol'],
          summarize_labels=False):
    """
    Read a WFDB annotation file record_name.extension and return an
    Annotation object.

    Parameters
    ----------
    record_name : str
        The record name of the WFDB annotation file. ie. for file '100.atr',
        record_name='100'.
    extension : str
        The annotatator extension of the annotation file. ie. for  file
        '100.atr', extension='atr'.
    sampfrom : int, optional
        The minimum sample number for annotations to be returned.
    sampto : int, optional
        The maximum sample number for annotations to be returned.
    shift_samps : bool, optional
        Specifies whether to return the sample indices relative to `sampfrom`
        (True), or sample 0 (False).
    pb_dir : str, optional
        Option used to stream data from Physiobank. The Physiobank database
        directory from which to find the required annotation file. eg. For
        record '100' in 'http://physionet.org/physiobank/database/mitdb':
        pb_dir='mitdb'.
    return_label_elements : list, optional
        The label elements that are to be returned from reading the annotation
        file. A list with at least one of the following options: 'symbol',
        'label_store', 'description'.
    summarize_labels : bool, optional
        If True, assign a summary table of the set of annotation labels
        contained in the file to the 'contained_labels' attribute of the
        returned object. This table will contain the columns:
        ['label_store', 'symbol', 'description', 'n_occurences']

    Returns
    -------
    annotation : Annotation
        The Annotation object. Call help(wfdb.Annotation) for the attribute
        descriptions.

    Notes
    -----
    For every annotation sample, the annotation file explictly stores the
    'sample' and 'symbol' fields, but not necessarily the others. When reading
    annotation files using this function, fields which are not stored in the
    file will either take their default values of 0 or None, or will be carried
    over from their previous values if any.

    Examples
    --------
    >>> ann = wfdb.rdann('sample-data/100', 'atr', sampto=300000)

    """

    return_label_elements = check_read_inputs(sampfrom, sampto,
                                              return_label_elements)

    # Read the file in byte pairs
    filebytes = load_byte_pairs(record_name, extension, pb_dir)

    # Get wfdb annotation fields from the file bytes
    (sample, label_store, subtype,
     chan, num, aux_note) = proc_ann_bytes(filebytes, sampto)

    # Get the indices of annotations that hold definition information about
    # the entire annotation file, and other empty annotations to be removed.
    potential_definition_inds, rm_inds = get_special_inds(sample, label_store,
                                                          aux_note)

    # Try to extract information describing the annotation file
    (fs,
     custom_labels) = interpret_defintion_annotations(potential_definition_inds,
                                                      aux_note)

    # Remove annotations that do not store actual sample and label information
    (sample, label_store, subtype,
     chan, num, aux_note) = rm_empty_indices(rm_inds, sample, label_store,
                                             subtype, chan, num, aux_note)

    # Convert lists to numpy arrays dtype='int'
    (sample, label_store, subtype,
     chan, num) = lists_to_int_arrays(sample, label_store, subtype, chan, num)

    # Try to get fs from the header file if it is not contained in the
    # annotation file
    if fs is None:
        try:
            rec = record.rdheader(record_name, pb_dir)
            fs = rec.fs
        except:
            pass

    # Create the annotation object
    annotation = Annotation(record_name=os.path.split(record_name)[1],
                            extension=extension, sample=sample,
                            label_store=label_store,  subtype=subtype,
                            chan=chan, num=num, aux_note=aux_note, fs=fs,
                            custom_labels=custom_labels)

    # Apply the desired index range
    if sampfrom > 0 and sampto is not None:
        annotation.apply_range(sampfrom=sampfrom, sampto=sampto)

    # If specified, obtain annotation samples relative to the starting
    # index
    if shift_samps and len(sample) > 0 and sampfrom:
        annotation.sample = annotation.sample - sampfrom

    # Get the set of unique label definitions contained in this
    # annotation
    if summarize_labels:
        annotation.get_contained_labels(inplace=True)

    # Set/unset the desired label values
    annotation.set_label_elements(return_label_elements)

    return annotation


def check_read_inputs(sampfrom, sampto, return_label_elements):

    if sampto and sampto <= sampfrom:
        raise ValueError("sampto must be greater than sampfrom")
    if sampfrom < 0:
        raise ValueError("sampfrom must be a non-negative integer")

    if isinstance(return_label_elements, str):
        return_label_elements = [return_label_elements]

    if set.union(set(ann_label_fields), set(return_label_elements))!=set(ann_label_fields):
        raise ValueError('return_label_elements must be a list containing one or more of the following elements:',label_types)

    return return_label_elements

# Load the annotation file 1 byte at a time and arrange in pairs
def load_byte_pairs(record_name, extension, pb_dir):
    # local file
    if pb_dir is None:
        with open(record_name + '.' + extension, 'rb') as f:
            filebytes = np.fromfile(f, '<u1').reshape([-1, 2])
    # physiobank file
    else:
        filebytes = download._stream_annotation(record_name+'.'+extension, pb_dir).reshape([-1, 2])

    return filebytes

#  Get regular annotation fields from the annotation bytes
def proc_ann_bytes(filebytes, sampto):

    # Base annotation fields
    sample, label_store, subtype, chan, num, aux_note = [], [], [], [], [], []

    # Indexing Variables

    # Total number of sample from beginning of record. Annotation bytes
    # only store sample_diff
    sample_total = 0
    # Byte pair index
    bpi = 0

    # Process annotations. Iterate across byte pairs.
    # Sequence for one ann is:
    # - SKIP pair (if any)
    # - samp + sym pair
    # - other pairs (if any)
    # The last byte pair of the file is 0 indicating eof.
    while (bpi < filebytes.shape[0] - 1):

        # Get the sample and label_store fields of the current annotation
        sample_diff, current_label_store, bpi = proc_core_fields(filebytes, bpi)
        sample_total = sample_total + sample_diff
        sample.append(sample_total)
        label_store.append(current_label_store)

        # Process any other fields belonging to this annotation

        # Flags that specify whether the extra fields need to be updated
        update = {'subtype':True, 'chan':True, 'num':True, 'aux_note':True}
        # Get the next label store value - it may indicate additional
        # fields for this annotation, or the values of the next annotation.
        current_label_store = filebytes[bpi, 1] >> 2

        while (current_label_store > 59):
            subtype, chan, num, aux_note, update, bpi = proc_extra_field(current_label_store, filebytes,
                                                                         bpi, subtype, chan, num,
                                                                         aux_note, update)

            current_label_store = filebytes[bpi, 1] >> 2

        # Set defaults or carry over previous values if necessary
        subtype, chan, num, aux_note = update_extra_fields(subtype, chan, num, aux_note, update)

        if sampto and sampto<sample_total:
            sample, label_store, subtype, chan, num, aux_note = rm_last(sample, label_store, subtype, chan, num, aux_note)
            break

    return sample, label_store, subtype, chan, num, aux_note

# Get the sample difference and store fields of the current annotation
def proc_core_fields(filebytes, bpi):

    label_store = filebytes[bpi, 1] >> 2

    # The current byte pair will contain either the actual d_sample + annotation store value,
    # or 0 + SKIP.

    # Not a skip - it is the actual sample number + annotation type store value
    if label_store != 59:
        sample_diff = filebytes[bpi, 0] + 256 * (filebytes[bpi, 1] & 3)
        bpi = bpi + 1
    # Skip. Note: Could there be another skip after the first?
    else:
        # 4 bytes storing dt
        sample_diff = 65536 * filebytes[bpi + 1,0] + 16777216 * filebytes[bpi + 1,1] \
             + filebytes[bpi + 2,0] + 256 * filebytes[bpi + 2,1]

        # Data type is long integer (stored in two's complement). Range -2**31 to 2**31 - 1
        if sample_diff > 2147483647:
            sample_diff = sample_diff - 4294967296

        # After the 4 bytes, the next pair's samp is also added
        sample_diff = sample_diff + filebytes[bpi + 3, 0] + 256 * (filebytes[bpi + 3, 1] & 3)

        # The label is stored after the 4 bytes. Samples here should be 0.
        label_store = filebytes[bpi + 3, 1] >> 2
        bpi = bpi + 4

    return sample_diff, label_store, bpi

def proc_extra_field(label_store, filebytes, bpi, subtype, chan, num, aux_note, update):
    """
    Process extra fields belonging to the current annotation.
    Potential updated fields: subtype, chan, num, aux_note
    """

    # aux_note and sub are reset between annotations. chan and num copy over
    # previous value if missing.

    # SUB
    if label_store == 61:
        # sub is interpreted as signed char.
        subtype.append(filebytes[bpi, 0].astype('i1'))
        update['subtype'] = False
        bpi = bpi + 1
    # CHAN
    elif label_store == 62:
        # chan is interpreted as un_signed char
        chan.append(filebytes[bpi, 0])
        update['chan'] = False
        bpi = bpi + 1
    # NUM
    elif label_store == 60:
        # num is interpreted as signed char
        num.append(filebytes[bpi, 0].astype('i1'))
        update['num'] = False
        bpi = bpi + 1
    # aux_note
    elif label_store == 63:
        # length of aux_note string. Max 256? No need to check other bits of
        # second byte?
        aux_notelen = filebytes[bpi, 0]
        aux_notebytes = filebytes[bpi + 1:bpi + 1 + int(np.ceil(aux_notelen / 2.)),:].flatten()
        if aux_notelen & 1:
            aux_notebytes = aux_notebytes[:-1]
        # The aux_note string
        aux_note.append("".join([chr(char) for char in aux_notebytes]))
        update['aux_note'] = False
        bpi = bpi + 1 + int(np.ceil(aux_notelen / 2.))

    return subtype, chan, num, aux_note, update, bpi


def update_extra_fields(subtype, chan, num, aux_note, update):
    """
    Update the field if the current annotation did not
    provide a value.

    - aux_note and sub are set to default values if missing.
    - chan and num copy over previous value if missing.
    """

    if update['subtype']:
        subtype.append(0)

    if update['chan']:
        if chan == []:
            chan.append(0)
        else:
            chan.append(chan[-1])
    if update['num']:
        if num == []:
            num.append(0)
        else:
            num.append(num[-1])

    if update['aux_note']:
        aux_note.append('')

    return subtype, chan, num, aux_note


rx_fs = re.compile("## time resolution: (?P<fs>\d+\.?\d*)")
rx_custom_label = re.compile("(?P<label_store>\d+) (?P<symbol>\S+) (?P<description>.+)")


def get_special_inds(sample, label_store, aux_note):
    """
    Get the indices of annotations that hold definition information about
    the entire annotation file, and other empty annotations to be removed.

    Note: There is no need to deal with SKIP annotations (label_store=59)
          which were already dealt with in proc_core_fields and hence not
          included here.
    """

    s0_inds = np.where(sample == np.int64(0))[0]
    note_inds = np.where(label_store == np.int64(22))[0]

    # sample = 0 with aux_note means there should be an fs or custom label definition.
    # Either way, they are to be removed.
    potential_definition_inds = set(s0_inds).intersection(note_inds)

    # Other indices which are not actual annotations.
    notann_inds = np.where(label_store == np.int64(0))[0]

    rm_inds = potential_definition_inds.union(set(notann_inds))

    return potential_definition_inds, rm_inds


def interpret_defintion_annotations(potential_definition_inds, aux_note):
    """
    Try to extract annotation definition information from annotation notes.
    Information that may be contained:
    - fs - sample=0, label_state=22, aux_note='## time resolution: XXX'
    - custom annotation label definitions
    """

    fs = None
    custom_labels = []

    if len(potential_definition_inds) > 0:
        i = 0
        while i<len(potential_definition_inds):
            if aux_note[i].startswith('## '):
                if not fs:
                    search_fs = rx_fs.findall(aux_note[i])
                    if search_fs:
                        fs = float(search_fs[0])
                        if round(fs, 8) == float(int(fs)):
                            fs = int(fs)
                        i += 1
                        continue
                if aux_note[i] == '## annotation type definitions':
                    i += 1
                    while aux_note[i] != '## end of definitions':
                        label_store, symbol, description = rx_custom_label.findall(aux_note[i])[0]
                        custom_labels.append((int(label_store), symbol, description))
                        i += 1
                    i += 1
            else:
                i += 1

    if not custom_labels:
        custom_labels = None

    return fs, custom_labels

def rm_empty_indices(*args):
    """
    Remove unwanted list indices. First argument is the list
    of indices to remove. Other elements are the lists
    to trim.
    """
    rm_inds = args[0]

    if not rm_inds:
        return args[1:]

    keep_inds = [i for i in range(len(args[1])) if i not in rm_inds]

    return [[a[i] for i in keep_inds] for a in args[1:]]

def lists_to_int_arrays(*args):
    """
    Convert lists to numpy int arrays
    """
    return [np.array(a, dtype='int') for a in args]

def rm_last(*args):
    """
    Remove the last index from each list
    """
    if len(args) == 1:
        return args[:-1]
    else:
        return [a[:-1] for a in args]
    return

## ------------- Annotation Field Specifications ------------- ##

"""
WFDB field specifications for each field. The indexes are the field
names.

Parameters
----------
allowed_types:
    Data types the field (or its elements) can be.
delimiter:
    The text delimiter that precedes the field in the header file.
write_required:
    Whether the field is required for writing a header (more stringent
    than origin WFDB library).
read_default:
    The default value for the field when read if any. Most fields do not
    have a default. The reason for the variation, is that we do not want
    to imply that some fields are present when they are not, unless the
    field is essential. See the notes.
write_default:
    The default value for the field to fill in before writing, if any.

Notes
-----
In the original WFDB package, certain fields have default values, but
not all of them. Some attributes need to be present for core
functionality, ie. baseline, whereas others are not essential, yet have
defaults, ie. base_time.

This inconsistency has likely resulted in the generation of incorrect
files, and general confusion. This library aims to make explicit,
whether certain fields are present in the file, by setting their values
to None if they are not written in, unless the fields are essential, in
which case an actual default value will be set.

The read vs write default values are different for 2 reasons:
1. We want to force the user to be explicit with certain important
   fields when writing WFDB records fields, without affecting
   existing WFDB headers when reading.
2. Certain unimportant fields may be dependencies of other
   important fields. When writing, we want to fill in defaults
   so that the user doesn't need to. But when reading, it should
   be clear that the fields are missing.

"""


# Allowed types of each Annotation object attribute.
ALLOWED_TYPES = {'record_name': (str), 'extension': (str),
                 'sample': (np.ndarray,), 'symbol': (list, np.ndarray),
                 'subtype': (np.ndarray,), 'chan': (np.ndarray,),
                 'num': (np.ndarray,), 'aux_note': (list, np.ndarray),
                 'fs': _header.float_types, 'label_store': (np.ndarray,),
                 'description':(list, np.ndarray),
                 'custom_labels': (pd.DataFrame, list, tuple),
                 'contained_labels':(pd.DataFrame, list, tuple)}

str_types = (str, np.str_)

# Elements of the annotation label
ann_label_fields = ('label_store', 'symbol', 'description')


class AnnotationClass(object):
    def __init__(self, extension, description, human_reviewed):

        self.extension = extension
        self.description = description
        self.human_reviewed = human_reviewed


ann_classes = [
    AnnotationClass('atr', 'Reference ECG annotations', True),

    AnnotationClass('blh', 'Human reviewed beat labels', True),
    AnnotationClass('blm', 'Machine beat labels', False),

    AnnotationClass('alh', 'Human reviewed alarms', True),
    AnnotationClass('alm', 'Machine alarms', False),

    AnnotationClass('qrsc', 'Human reviewed qrs detections', True),
    AnnotationClass('qrs', 'Machine QRS detections', False),

    AnnotationClass('bph', 'Human reviewed BP beat detections', True),
    AnnotationClass('bpm', 'Machine BP beat detections', False),

    #AnnotationClass('alh', 'Human reviewed BP alarms', True),
    #AnnotationClass('alm', 'Machine BP alarms', False),
    # separate ecg and other signal category alarms?
    # Can we use signum to determine the channel it was triggered off?

    #ppg alarms?
    #eeg alarms?
]

ann_class_table = pd.DataFrame({'extension':[ac.extension for ac in ann_classes], 'description':[ac.description for ac in ann_classes],
                                 'human_reviewed':[ac.human_reviewed for ac in ann_classes]})
ann_class_table.set_index(ann_class_table['extension'].values, inplace=True)
ann_class_table = ann_class_table[['extension', 'description', 'human_reviewed']]

# Individual annotation labels
class AnnotationLabel(object):
    def __init__(self, label_store, symbol, short_description, description):
        self.label_store = label_store
        self.symbol = symbol
        self.short_description = short_description
        self.description = description

    def __str__(self):
        return str(self.label_store)+', '+str(self.symbol)+', '+str(self.short_description)+', '+str(self.description)

ann_labels = [
    AnnotationLabel(0, " ", 'NOTANN', 'Not an actual annotation'),
    AnnotationLabel(1, "N", 'NORMAL', 'Normal beat'),
    AnnotationLabel(2, "L", 'LBBB', 'Left bundle branch block beat'),
    AnnotationLabel(3, "R", 'RBBB', 'Right bundle branch block beat'),
    AnnotationLabel(4, "a", 'ABERR', 'Aberrated atrial premature beat'),
    AnnotationLabel(5, "V", 'PVC', 'Premature ventricular contraction'),
    AnnotationLabel(6, "F", 'FUSION', 'Fusion of ventricular and normal beat'),
    AnnotationLabel(7, "J", 'NPC', 'Nodal (junctional) premature beat'),
    AnnotationLabel(8, "A", 'APC', 'Atrial premature contraction'),
    AnnotationLabel(9, "S", 'SVPB', 'Premature or ectopic supraventricular beat'),
    AnnotationLabel(10, "E", 'VESC', 'Ventricular escape beat'),
    AnnotationLabel(11, "j", 'NESC', 'Nodal (junctional) escape beat'),
    AnnotationLabel(12, "/", 'PACE', 'Paced beat'),
    AnnotationLabel(13, "Q", 'UNKNOWN', 'Unclassifiable beat'),
    AnnotationLabel(14, "~", 'NOISE', 'Signal quality change'),
    # AnnotationLabel(15, None, None, None),
    AnnotationLabel(16, "|", 'ARFCT',  'Isolated QRS-like artifact'),
    # AnnotationLabel(17, None, None, None),
    AnnotationLabel(18, "s", 'STCH',  'ST change'),
    AnnotationLabel(19, "T", 'TCH',  'T-wave change'),
    AnnotationLabel(20, "*", 'SYSTOLE',  'Systole'),
    AnnotationLabel(21, "D", 'DIASTOLE',  'Diastole'),
    AnnotationLabel(22, '"', 'NOTE',  'Comment annotation'),
    AnnotationLabel(23, "=", 'MEASURE',  'Measurement annotation'),
    AnnotationLabel(24, "p", 'PWAVE',  'P-wave peak'),
    AnnotationLabel(25, "B", 'BBB',  'Left or right bundle branch block'),
    AnnotationLabel(26, "^", 'PACESP',  'Non-conducted pacer spike'),
    AnnotationLabel(27, "t", 'TWAVE',  'T-wave peak'),
    AnnotationLabel(28, "+", 'RHYTHM',  'Rhythm change'),
    AnnotationLabel(29, "u", 'UWAVE',  'U-wave peak'),
    AnnotationLabel(30, "?", 'LEARN',  'Learning'),
    AnnotationLabel(31, "!", 'FLWAV',  'Ventricular flutter wave'),
    AnnotationLabel(32, "[", 'VFON',  'Start of ventricular flutter/fibrillation'),
    AnnotationLabel(33, "]", 'VFOFF',  'End of ventricular flutter/fibrillation'),
    AnnotationLabel(34, "e", 'AESC',  'Atrial escape beat'),
    AnnotationLabel(35, "n", 'SVESC',  'Supraventricular escape beat'),
    AnnotationLabel(36, "@", 'LINK',  'Link to external data (aux_note contains URL)'),
    AnnotationLabel(37, "x", 'NAPC',  'Non-conducted P-wave (blocked APB)'),
    AnnotationLabel(38, "f", 'PFUS',  'Fusion of paced and normal beat'),
    AnnotationLabel(39, "(", 'WFON',  'Waveform onset'),
    AnnotationLabel(40, ")", 'WFOFF',  'Waveform end'),
    AnnotationLabel(41, "r", 'RONT',  'R-on-T premature ventricular contraction'),
    # AnnotationLabel(42, None, None, None),
    # AnnotationLabel(43, None, None, None),
    # AnnotationLabel(44, None, None, None),
    # AnnotationLabel(45, None, None, None),
    # AnnotationLabel(46, None, None, None),
    # AnnotationLabel(47, None, None, None),
    # AnnotationLabel(48, None, None, None),
    # AnnotationLabel(49, None, None, None),
]


ann_label_table = pd.DataFrame({'label_store':np.array([al.label_store for al in ann_labels], dtype='int'), 'symbol':[al.symbol for al in ann_labels],
                               'description':[al.description for al in ann_labels]})
ann_label_table.set_index(ann_label_table['label_store'].values, inplace=True)
ann_label_table = ann_label_table[['label_store','symbol','description']]

