import libs.wfdb as wfdb
import matplotlib.pyplot as plt
import numpy as np

# 画心电图
def draw_ecg(x):
    plt.plot(x)
    plt.show()

# 读取心电图数据
def read_ecg_data():
    '''
    读取心电信号文件
    sampfrom: 设置读取心电信号的 起始位置，sampfrom=0表示从0开始读取，默认从0开始
    sampto：设置读取心电信号的 结束位置，sampto = 1500表示从1500出结束，默认读到文件末尾
    channel_names：设置设置读取心电信号名字，必须是列表，channel_names=['MLII']表示读取MLII导联线
    channels：设置读取第几个心电信号，必须是列表，channels=[0, 3]表示读取第0和第3个信号，注意信号数不确定
    :return:
    '''
    record = wfdb.rdrecord('../ecg_data/101', sampfrom=0, sampto = 1500)
    # 仅仅读取“MLII”信号
    # record = wfdb.rdrecord('../ecg_data/101', sampto=1500, channel_names=['MLII'])
    # 仅仅读取第0个信号（MLII）
    # record = wfdb.rdrecord('../ecg_data/101', sampfrom=0, sampto=1500, channels=[0])

    # 查看record类型
    # print(type(record))
    # 查看类中的方法和属性
    # print(dir(record))

    # 获得心电导联线信号，本文获得是MLII和V1信号数据
    print(record.p_signal)
    print(np.shape(record.p_signal))
    # 查看导联线信号长度，本文信号长度1500
    print(record.sig_len)
    # 查看文件名
    print(record.record_name)
    # 查看导联线条数，本文为导联线条数2
    print(record.n_sig)
    # 查看信号名称（列表），本文导联线名称['MLII', 'V1']
    print(record.sig_name)
    # 查看采用率
    print(record.fs)


    print("***************")

    '''
    读取注解文件
    sampfrom: 设置读取心电信号的 起始位置，sampfrom=0表示从0开始读取，默认从0开始
    sampto：设置读取心电信号的 结束位置，sampto = 1500表示从1500出结束，默认读到文件末尾
    '''
    annotation = wfdb.rdann('../ecg_data/102', 'atr')
    # 查看annotation类型
    # print(type(annotation))
    # 查看类中的方法和属性
    # print(dir(annotation))

    # 标注每一个心拍的R波的尖锋位置，与心电信号对应
    print(annotation.sample)
    # 标注每一个心拍的类型N，L，R等等
    print(annotation.symbol)
    # 被标注的数量
    print(annotation.ann_len)
    # 被标注的文件名
    print(annotation.record_name)

    # 查看心拍的类型
    # print(wfdb.show_ann_labels())

    draw_ecg(record.p_signal)

if __name__ == "__main__":
    read_ecg_data()
