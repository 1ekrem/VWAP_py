import numpy as np
import pandas as pd

import time
from datetime import datetime
from datetime import timedelta
from datetime import date as date
from datetime import time as dt_time

import scipy.interpolate
from sklearn.linear_model import Lasso
from statsmodels.tsa.arima_model import ARMA

from math import ceil
import warnings
from os import listdir

def cov(a,b):

    a_mean = np.mean(a)
    b_mean = np.mean(b)
    sum = 0
    for i in range(0,len(a)):
        sum += (a[i] - a_mean)*(b[i] - b_mean)
    
    return sum / (len(a) - 1)


def getL(y):
    """By linear regression predict the next value"""

    x = np.array(range(0,len(y)))
    b = cov(x,y) / cov(x,x)
    a = np.mean(y) - b * np.mean(x)
    
    return b * len(y) + a


def rolling_mean(a,n = 5):

    x = [0.] * (len(a)-n + 1)
    for i in range(n,len(a) +  1):
        x[i - n] = a[i-n:i].mean()
    
    return x


def rolling_linear(a, n = 5):
    
    x = [0.] * (len(a)-n + 1)
    for i in range(n , len(a)+ 1):
        x[i - n] = getL(a[i-n:i])
    
    return x


def get_log(r_vol,p_vol,p_per): 
    
    return {'r_vol':r_vol, 'p_vol':p_vol, 'p_per':p_per}


def datetime_range(T_START_TIME, T_END_TIME ,delta):
    
    current = T_START_TIME
    end = T_END_TIME
    while current < end:
        yield current
        current += delta

class VWAP_handler(object):
    """
    a single VWAP object will track and predict one ticker
    """

    def __init__(self, interval, tickers, data_path ,lasso_lambda = 812314, n_tick_threshold = 1000, market_close_time = '15:00:00'):

        self.tickers = {}
        self._params = {
            # 'TODAY': date.today(),
            'TODAY': datetime.strptime(today_for_test, "%Y-%m-%d")
            'T_START_TIME': dt_time(hour = 9, minute = 30, second = 0, microsecond = 0),
            'T_END_TIME': datetime.strptime(market_close_time, '%H:%M:%S').time(),
            'LASSO_LAMBDA': lasso_lambda,
            'N_TICK_THRESHOLD': n_tick_threshold, # Tracey to notice
            'DATA_PATH': data_path  
        }

        for ticker in tickers:
            self.tickers[ticker] = VWAP(interval, ticker, self._params)
        
class VWAP(object):
    """
    a single VWAP object will track and predict one ticker
    """


    def __init__(self, interval, ticker, kwargs):
        
        if (interval % 5 != 0) or (7200 % interval != 0):
            raise ValueError('interval must be a multiple of 5 secs and can divide 2 hours')

        # ugly!
        tickercsv = ticker + '.csv'
        if not tickercsv in listdir(kwargs['DATA_PATH']):
            raise Exception('no data for %s' % ticker)

        dates = set(listdir(kwargs['DATA_PATH']))

        self.TODAY = kwargs['TODAY']
        # self.TODAY = datetime.strptime(today_for_test, "%Y-%m-%d")  # Tracey to notice
        self.T_START_TIME = kwargs['T_START_TIME']
        self.T_START_NANO_SEC = time.mktime(datetime.combine(self.TODAY, dt_time(hour = 9, minute = 30, second = 0, microsecond = 0) ).timetuple())
        # self.T_START_TIME = self.TODAY.replace(hour = 9, minute = 30, second = 0, microsecond = 0)
        self.T_END_TIME = kwargs['T_END_TIME']
        self.T_END_SECS = total.seconds(self.T_END_TIME - self.T_START_TIME)
        # self.T_END_TIME = self.TODAY.replace(hour = 15, minute = 00, second = 0, microsecond = 0)
        self.LASSO_LAMBDA = kwargs['LASSO_LAMBDA']
        self.N_TICK_THRESHOLD = kwargs['N_TICK_THRESHOLD'] # Tracey to notice
        self.DATA_PATH = kwargs['DATA_PATH'] + self.TODAY.strftime("%Y%m%d") + '/'
        # self.DATA_PATH = './data_path/' # Tracey to notice
        self._interval = interval
        self._interval_timedelta = timedelta(seconds = self._interval)
        self._am_n_interval = int(self.HALFTIME / self._interval_timedelta)
        self._n_interval = self._am_n_interval + ceil((self.T_END_TIME - dt_time(hour = 13, 
                                minute = 0, second = 0, microsecond = 0)) / interval) 
        self._features_to_train = np.ones((11,3),dtype=float) # CA, M, L, A
        self._histo_volume = np.full((10, self._n_interval),0, dtype=float)  # historical trading volume        
        self._intraday_percentage = [1 / self._n_interval] * self._n_interval  # notice .sum() =self._n_interval
        # self._AR_pars = np.array([1,0],dtype =float) # (u and phi)
        self._AR_pars = [0., 1.] 
        self._CA_today = 0
        self._predicted_V = 0.
        self._is_V_predicted = 0
        self._last_update = 0
        self._iter = 0       
        self._datetime_index = ( [str(dt) for dt in datetime_range(self.T_START_TIME, 
                                dt_time(hour = 11, minute = 30, second = 0, 
                                microsecond = 0),timedelta(seconds = self._interval))] + 
                                [str(dt) for dt in datetime_range(dt_time(hour = 13, 
                                minute = 0, second = 0, microsecond = 0), 
                                self.T_END_TIME,timedelta(seconds = self._interval))])
        self._today_vol = [0.] * self._n_interval
        self._p_per = [0.] * self._n_interval
        self._p_vol = [0] * self._n_interval
        self._VWAP_log = {}

        histo_date = self.TODAY
        past_days = 0
        x_output = np.concatenate(np.arange(0 + self._interval , 7200 + self._interval, self._interval), 
                            np.arange(12600 + self._interval, self.T_END_SECS, self._interval), np.array([self.T_END_SECS]))

        iter = 1
        
        while iter < 11:

            if not bool(dates):
                raise Exception('Insufficient historical data')

            histo_date = histo_date - timedelta(days = 1)
            past_days += 1

            if history_date.weekday() in set([5,6]):
                continue

            if str(histo_date) not in dates:
                continue
            dates.remove(str(histo_date))

            try:
                dat = pd.read_csv(self.DATA_PATH + tickercsv, header = 0)
            except Exception:
                print(print('Error in reading %s for %s, go to the previous day.' % (tickerfile, str(histo_date))))
                continue

            if dat.shape[0] < self.N_TICK_THRESHOLD:
                print('%s in %s has few data for prediction' % (tickerfile, str(histo_date)))
                continue

            if past_days > 20:
                warnings.warn('Lack historical data. Time span of data for predicting intraday_volume of today has exceeded 20 days.'
                                'We are using data %d days from today' % past_days) 

            try:
                dat.Nano = dat.Nano / 1e9 - time.mktime(datetime.combine(histo_date, dt_time(hour = 9, minute = 30, second = 0, microsecond = 0)).timetuple())
                dat = dat.as_matrix(columns = ['Nano', 'Volume']) # there will be Microsecond
                datCA = dat[dat[:,0] < 0][-1,1] # Tracey to notice
                if datCA < 1: # no data or no trade ?
                    continue
                
                self._features_to_train[10 - iter,0] = datCA
                dat = dat[dat[:,0] > 0]

                # Tracey by reviewing the data from ctp finds it impossible
                if any( 7200 < t < 7230 for t in dat[:,0]): # tracey_to_notice
                    dat = np.vstack( (dat[dat[:, 0] < 7200], [7200, dat[(dat[:,0] >= 7200)*(dat[:,0] < 7230),1][-1] ], dat[dat[:, 0] > 7230]))
                if any(t >= 198000 for t in dat[:,0]):
                    dat = np.vstack((dat[dat[:, 0] < 19800], [19800,dat[dat[:,0] >= 19800,1][-1]])) # tracey to notice

                dat[-1,0] = 198000
                x_input = np.append(0, dat[:,0])
                # volume_cumsum = np.append(0,dat[:,1].cumsum())
                volume_cumsum = np.append(0, dat[:, 1]) # tracey to notice
                y_interp = scipy.interpolate.interp1d(x_input,volume_cumsum) # ,interval)
                intraday_volume = y_interp(x_output)
                intraday_volume = np.append(intraday_volume[0],(intraday_volume[1:] - intraday_volume[:-1]))
                self._histo_volume[10 - iter] = intraday_volume
            except Exception:
                print('Error when read file %s, you may check its format' % filename)
                continue

            iter += 1

        volume_sums = np.zeros(5,dtype=float)
        while iter < 16:

            if not bool(dates):
                raise Exception('Insufficient historical data')

            history_date = history_date - timedelta(days = 1)
            past_days += 1

            if history_date.weekday() in set([5,6]):
                continue

            if str(histo_date) not in dates:
                continue
            dates.remove(str(histo_date))

            try:
                dat = pd.read_csv(self.DATA_PATH + tickercsv, header = 0)
            except Exception:
                print('Error in reading %s for %s, go to the previous day.' % (tickercsv, str(histo_date)))
                continue     

            if dat.shape[0] < self.N_TICK_THRESHOLD:
                print('%s in %s has few data for prediction' % (tickercsv, str(histo_date)))
                continue   

            if past_days > 30:
                warnings.warn('Lack efficacious historical data. Time span of data for predicting total trading volume of today has exceeded 30 days.')

            try:
                dat.Nano = dat.Nano / 1e9 - time.mktime(datetime.combine(histo_date, dt_time(hour = 9, minute = 30, second = 0, microsecond = 0)).timetuple())                
                dat = dat.as_matrix(columns = ['Nano', 'Volume']) # there will be Microsecond
                volume_sums[15 - iter] = dat[ (dat[:,0] > 0) * (dat[:,0] < self.T_END_SECS),1][-1] # Tracey to notice
            except Exception:
                print('Error to read file %s, you may check its format' % tickercsv)
                continue

        iter += 1

        # preparing sample for predicting today's total volume
        self.volume_to_train = self._histo_volume.sum(axis = 1)
        volume_sums = np.append(volume_sums, self.volume_to_train)
        self._features_to_train[:,1] = rolling_mean(volume_sums)
        self._features_to_train[:,2] = rolling_linear(volume_sums)

        # get intraday pattern and intialize intraday prediction
        intraday_mean = self._histo_volume.mean(axis = 0)
        self._p_vol[0] = float(intraday_mean[0])
        self._intraday_percentage = list(np.divide(intraday_mean, intraday_mean.sum()) * self._n_interval)
        
        if any( i < 1 / (self._n_interval * 10 ) for i in self._intraday_percentage):
            warnings.warn('adjust intraday trading volume pattern for irregular data')
        tmp = np.divide(intraday_mean, intraday_mean.sum()) * self._n_interval
        if np.any(tmp < 0.1):
            warnings.warn('adjust intraday trading volume pattern for irregular data')
            tmp[tmp >= 0.1] = tmp[tmp > 0.1] * sum(self._n_interval - 0.1 * len(tmp[tmp < 0.1]) / sum(tmp[tmp >= 0.1]))
            tmp[tmp < 0.1] = 0.1
        self._intraday_percentage = list(tmp)
        self._p_per[0] = self._intraday_percentage[0] / self._n_interval
        self._VWAP_log[self._datetime_index[0]] = get_log(None, self._p_vol[0], self._p_per[0])         
        
        # compute AR
        arma = ARMA( self._histo_volume[-1] / self._intraday_percentage, order = (1,0))
        self._AR_pars = arma.fit().params.tolist()

    def pred_V(self):
        
        if self._CA_today == 0:
            self._features_to_train[10,0] = self._features_to_train[:,0].sum()
        else:
            self._features_to_train[10,0] = self._CA_today
        
        lm = Lasso(alpha = self.LASSO_LAMBDA)
        lm.fit(self._features_to_train[0:-1,:],self.volume_to_train)
        self._predicted_V = int(lm.predict(self._features_to_train[-1].reshape(1,-1))[0])
        if self._predicted_V < 0:
            warnings.warn('We some how get a exceeding low volume prediction for today. We strongly urge you check your tick data.')
            self._predicted_V = 1 # Tracey to notice
        self._is_V_predicted = 1
        print('finish: pred_V')

    def get_predict(self):
        return(self._VWAP_log)

    def push_tick(self, nano, volume):

        sec_time = nano / 1e9 - self.T_START_NANO_SEC

        if sec_time < 0:
            self.CAtoday += volume
        
        elif sec_time < self.T_END_SECS:
            
            if not self.is_V_predicted:
                self.pred_V()
            
            iter = int(sec_time / self._interval)
            
            if iter > self._semi_n_interval: # in the afternoon
                iter -= int(self._n_interval * 3 / 8)
            
            self._today_vol[iter] += volume
            self._iter = iter
            
            if self._iter == self._last_update:
                pass
            
            elif self._iter - self._last_update == 1:
                self._VWAP_log[self._datetime_index[self._last_update]] = get_log(self._today_vol[self._last_update], self._p_vol[self._last_update], self._p_per[self._last_update])
                self._p_vol[self._iter] = int ((self._AR_pars[1] * (self._today_vol[self._last_update] / self._intraday_percentage[self._last_update] - self._AR_pars[0] ) + self._AR_pars[0] ) * self._intraday_percentage[self._iter])
                
                if self._iter < (self._n_interval - 1):
                    self._p_per[self._iter] = self._p_vol[self._iter] * (1 - sum(self._p_per[0:self._iter])) / (self._predicted_V * (1 - sum(self._intraday_percentage[0:self._iter])/ self._n_interval ))
                else:
                    self._p_per[self._n_interval - 1] = 1 - sum(self._p_per[0:(self._n_interval - 1)])
                
                self._VWAP_log[self._datetime_index[self._iter]] = get_log(None, self._p_vol[self._iter], self._p_per[self._iter])
                self._last_update = self._iter
            
            elif self._iter - self._last_update > 1:
                warnings.warn('Over %d secs without receiving data' % self.interval)
                self._today_vol[iter] =+ volume
                self._today_vol[self._last_update:self._iter] = [a + b for a, b in zip(self._today_vol[self._last_update:self._iter], [volume * s / sum(self._intraday_percentage[self._last_update:self._iter]) for s in self._intraday_percentage[self._last_update:self._iter]])]
                
                for i in range(self._last_update, self._iter):
                    self._VWAP_log[self._datetime_index[i]] = get_log(self._today_vol[i], self._p_vol[i], self._p_per[i])
                    self._p_vol[i + 1] = int ((self._AR_pars[1] * (self._today_vol[i] / self._intraday_percentage[i] - self._AR_pars[0] ) + self._AR_pars[0] ) * self._intraday_percentage[i + 1]) 
                    if i + 1 < (self._n_interval - 1):
                        self._p_per[i + 1] = self._p_vol[i + 1] * (1 - sum(self._p_per[0:(i + 1)])) / (self._predicted_V * (1 - sum(self._intraday_percentage[0:(i + 1)])/ self._n_interval ))
                    else:
                        self._p_per[self._n_interval - 1] = 1 - sum(self._p_per[0:(self._n_interval - 1)])
                    self._VWAP_log[self._datetime_index[i + 1]] = get_log(None, self._p_vol[i + 1], self._p_per[i + 1])
                self._last_update = self._iter                    
            
            else: # when self._iter < self._last_update, we only update real volume
                pass
        
        else: # datetime > T_END_TIME
            if self._iter - self._last_update == 1:
                pass 
            else:
                warnings.warn('Over %d secs without receiving data' % self.interval)
                self._today_vol[iter] =+ volume
                self._today_vol[self._last_update:self._iter] = [a + b for a, b in zip(self._today_vol[self._last_update:self._iter], [volume * s / sum(self._intraday_percentage[self._last_update:self._iter]) for s in self._intraday_percentage[self._last_update:self._iter]])]
                
                for i in range(self._last_update, self._n_interval - 1):
                    self._VWAP_log[self._datetime_index[i]] = get_log(self._today_vol[i], self._p_vol[i], self._p_per[i])
                    self._p_vol[i + 1] = int ((self._AR_pars[1] * (self._today_vol[i] / self._intraday_percentage[i] - self._AR_pars[0] ) + self._AR_pars[0] ) * self._intraday_percentage[i + 1]) 
                    
                    if i + 1 < (self._n_interval - 1):
                        self._p_per[i + 1] = self._p_vol[i + 1] * (1 - sum(self._p_per[0:(i + 1)])) / (self._predicted_V * (1 - sum(self._intraday_percentage[0:(i + 1)])/ self._n_interval ))
                    else:
                        self._p_per[self._n_interval - 1] = 1 - sum(self._p_per[0:(self._n_interval - 1)])
                    
                    self._VWAP_log[self._datetime_index[i + 1]] = get_log(None, self._p_vol[i + 1], self._p_per[i + 1])
                
                self._last_update = self._n_interval - 1 
                
            self._today_vol[self._n_interval - 1] += volume 
            self._VWAP_log[self._datetime_index[self._n_interval - 1]] = get_log(self._today_vol[self._n_interval - 1], self._p_vol[self._n_interval - 1], self._p_per[self._n_interval - 1])

if __name__ == "__main__":
    
    interval = 60

    today_for_test = '20170714'

    Tracey = VWAPs(interval, ['SH600884'], lasso_lambda = 812314)

    a = Tracey['SH600884']

    print('DoneVWAP')

    df = pd.read_csv(a.DATA_PATH + "SH6008842017-07-13.csv")
    df.columns = ['DateTime','Volume']

    def toInput(t):
        x = t[0]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 
        y = t[1]
        x = "2017-07-14 " + x
        x = datetime.strptime(x, "%Y-%m-%d %H:%M:%S")
        return x,y

    for i, row in enumerate(df.values.tolist()):
        a.push_tick(*toInput(row))

    today_vol = np.array(a.today_vol)
    vwap = np.array(a.predp)
    twap = np.array([1 / len(a.predp)] * len(a.predp))
    s = np.array(a.intraday_percentage)

    print(interval)

    print('abs')

    print(sum( np.absolute(today_vol / sum(today_vol) - twap)) )
    print(sum( np.absolute(today_vol / sum(today_vol) - vwap)))
    print(sum( np.absolute(today_vol / sum(today_vol) - s / len(a.predp))))

    print(interval)

