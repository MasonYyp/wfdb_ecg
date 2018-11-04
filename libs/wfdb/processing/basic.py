import numpy as np
from scipy import signal

from ..io.annotation import Annotation


def resample_ann(resampled_t, ann_sample):
    """
    Compute the new annotation indices

    Parameters
    ----------
    resampled_t : numpy array
        Array of signal locations as returned by scipy.signal.resample
    ann_sample : numpy array
        Array of annotation locations

    Returns
    -------
    resampled_ann_sample : numpy array
        Array of resampled annotation locations

    """
    tmp = np.zeros(len(resampled_t), dtype='int16')
    j = 0
    tprec = resampled_t[j]
    for i, v in enumerate(ann_sample):
        while True:
            d = False
            if v < tprec:
                j -= 1
                tprec = resampled_t[j]

            if j+1 == len(resampled_t):
                tmp[j] += 1
                break

            tnow = resampled_t[j+1]
            if tprec <= v and v <= tnow:
                if v-tprec < tnow-v:
                    tmp[j] += 1
                else:
                    tmp[j+1] += 1
                d = True
            j += 1
            tprec = tnow
            if d:
                break

    idx = np.where(tmp>0)[0].astype('int64')
    res = []
    for i in idx:
        for j in range(tmp[i]):
            res.append(i)
    assert len(res) == len(ann_sample)

    return np.asarray(res, dtype='int64')


def resample_sig(x, fs, fs_target):
    """
    Resample a signal to a different frequency.

    Parameters
    ----------
    x : numpy array
        Array containing the signal
    fs : int, or float
        The original sampling frequency
    fs_target : int, or float
        The target frequency

    Returns
    -------
    resampled_x : numpy array
        Array of the resampled signal values
    resampled_t : numpy array
        Array of the resampled signal locations

    """

    t = np.arange(x.shape[0]).astype('float64')

    if fs == fs_target:
        return x, t

    new_length = int(x.shape[0]*fs_target/fs)
    resampled_x, resampled_t = signal.resample(x, num=new_length, t=t)
    assert resampled_x.shape == resampled_t.shape and resampled_x.shape[0] == new_length
    assert np.all(np.diff(resampled_t) > 0)

    return resampled_x, resampled_t


def resample_singlechan(x, ann, fs, fs_target):
    """
    Resample a single-channel signal with its annotations

    Parameters
    ----------
    x: numpy array
        The signal array
    ann : wfdb Annotation
        The wfdb annotation object
    fs : int, or float
        The original frequency
    fs_target : int, or float
        The target frequency

    Returns
    -------
    resampled_x : numpy array
        Array of the resampled signal values
    resampled_ann : wfdb Annotation
        Annotation containing resampled annotation locations

    """

    resampled_x, resampled_t = resample_sig(x, fs, fs_target)

    new_sample = resample_ann(resampled_t, ann.sample)
    assert ann.sample.shape == new_sample.shape

    resampled_ann = Annotation(record_name=ann.record_name,
                               extension=ann.extension,
                               sample=new_sample,
                               symbol=ann.symbol,
                               subtype=ann.subtype,
                               chan=ann.chan,
                               num=ann.num,
                               aux_note=ann.aux_note,
                               fs=fs_target)

    return resampled_x, resampled_ann


def resample_multichan(xs, ann, fs, fs_target, resamp_ann_chan=0):
    """
    Resample multiple channels with their annotations

    Parameters
    ----------
    xs: numpy array
        The signal array
    ann : wfdb Annotation
        The wfdb annotation object
    fs : int, or float
        The original frequency
    fs_target : int, or float
        The target frequency
    resample_ann_channel : int, optional
        The signal channel used to compute new annotation indices

    Returns
    -------
    resampled_xs : numpy array
        Array of the resampled signal values
    resampled_ann : wfdb Annotation
        Annotation containing resampled annotation locations

    """
    assert resamp_ann_chan < xs.shape[1]

    lx = []
    lt = None
    for chan in range(xs.shape[1]):
        resampled_x, resampled_t = resample_sig(xs[:, chan], fs, fs_target)
        lx.append(resampled_x)
        if chan == resamp_ann_chan:
            lt = resampled_t

    new_sample = resample_ann(lt, ann.sample)
    assert ann.sample.shape == new_sample.shape

    resampled_ann = Annotation(record_name=ann.record_name,
                               extension=ann.extension,
                               sample=new_sample,
                               symbol=ann.symbol,
                               subtype=ann.subtype,
                               chan=ann.chan,
                               num=ann.num,
                               aux_note=ann.aux_note,
                               fs=fs_target)

    return np.column_stack(lx), resampled_ann


def normalize_bound(sig, lb=0, ub=1):
    """
    Normalize a signal between the lower and upper bound

    Parameters
    ----------
    sig : numpy array
        Original signal to be normalized
    lb : int, or float
        Lower bound
    ub : int, or float
        Upper bound

    Returns
    -------
    x_normalized : numpy array
        Normalized signal

    """

    mid = ub - (ub - lb) / 2
    min_v = np.min(sig)
    max_v = np.max(sig)
    mid_v =  max_v - (max_v - min_v) / 2
    coef = (ub - lb) / (max_v - min_v)
    return sig * coef - (mid_v * coef) + mid


def smooth(sig, window_size):
    """
    Apply a uniform moving average filter to a signal

    Parameters
    ----------
    sig : numpy array
        The signal to smooth.
    window_size : int
        The width of the moving average filter.

    """
    box = np.ones(window_size)/window_size
    return np.convolve(sig, box, mode='same')


def get_filter_gain(b, a, f_gain, fs):
    """
    Given filter coefficients, return the gain at a particular
    frequency.

    Parameters
    ----------
    b : list
        List of linear filter b coefficients
    a : list
        List of linear filter a coefficients
    f_gain : int or float, optional
        The frequency at which to calculate the gain
    fs : int or float, optional
        The sampling frequency of the system

    """
    # Save the passband gain
    w, h = signal.freqz(b, a)
    w_gain = f_gain * 2 * np.pi / fs

    ind = np.where(w >= w_gain)[0][0]
    gain = abs(h[ind])

    return gain
