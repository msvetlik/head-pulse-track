import time

import numpy as np
import cv2
from imutils import face_utils
import dlib
from face import FacePoints
from tracking import TrackPoints

import matplotlib.pyplot as plt


from scipy import interpolate, signal, optimize
from scipy.fftpack import fft, ifft, fftfreq, fftshift

from sklearn.decomposition import PCA

from scipy.signal import find_peaks


def draw_str(dst, target, s):
    x, y = target
    cv2.putText(dst, s, (x+1, y+1), cv2.FONT_HERSHEY_PLAIN, 1.0, (0, 0, 0), thickness = 2, lineType=cv2.LINE_AA)
    cv2.putText(dst, s, (x, y), cv2.FONT_HERSHEY_PLAIN, 1.0, (255, 255, 255), lineType=cv2.LINE_AA)



def get_diffs(traces, fps):
    # Filter traces get 4sec or long nyquist freq for 0.5 hz -> 1 hZ
    traces = [trace for trace in traces if len(trace) > 2*fps]
    trace_max_len = max( [len(trace) for trace in traces] )

    #trace_max_len = 300
    #TODO: This is quickfix
    traces = [trace for trace in traces if len(trace) == trace_max_len]   

    # Calculate y movement of each
    displacements = []
    #displacements = np.array([[]])
    for trace in traces:
        trace = np.array(trace)

        y_pts = trace[:, 1]
        # Pad array to standart lenght
        len_diff = trace_max_len-len(y_pts)
        if len_diff > 0:
            pass
            print('Padded', len_diff)    
        y_pts = np.pad(y_pts, (len_diff, 0), 'edge')
        
        displace = np.diff(y_pts) # y coordinates
        displacements.append(displace)

    if len(displacements) > 0:
        displacements = np.stack(displacements, axis=0)

    return displacements

def get_y(traces):
    # Filter traces get 4sec or long nyquist freq for 0.5 hz -> 1 hZ
    traces = [trace for trace in traces if len(trace) > 2*fps]
    trace_max_len = max( [len(trace) for trace in traces] )

    #trace_max_len = 300
    #TODO: This is quickfix
    traces = [trace for trace in traces if len(trace) == trace_max_len]

    # Calculate y movement of each
    ys = []
    #displacements = np.array([[]])
    for trace in traces:
        trace = np.array(trace)[:, 1]

        ys.append(trace)
    return np.stack(ys, axis=0)

# Filter Signal
def filter_signal(signal_data, fs=30, low_c=0.75, high_c=2.0):

    #fs = 30 # Fps
    # number of signal points
    N = len(signal_data)
    # sample spacing
    T = 1.0 / fs

    #Draw signal
    #t = np.arange(len(displace))/fps
    t = np.linspace(0.0, T*N, N)

    # Filter signal
    fc = np.array([low_c, high_c])  # Cut-off frequency of the filter
    # 0.75 hz - 2 hz => 45bpm - 120bpm

    w = fc / (fs / 2) # Normalize the frequency
    b, a = signal.butter(5, w, 'bandpass')

    filter_output = signal.filtfilt(b, a, signal_data)
    
    return filter_output


def filter_out(displacements, fps, low_c=0.5, high_c=2.0):
    filtered_signals = []

    for signal_data in displacements:
        filter_out = filter_signal(signal_data, fs=fps, low_c=low_c, high_c=high_c)
        filtered_signals.append(filter_out)

    if len(filtered_signals) > 0:
        filtered_signals = np.stack(filtered_signals, axis=0)

    return filtered_signals[:-fps]

def get_mean(filtered_signals, fps, show=True):
    if len(filtered_signals) < 5:
        return 0
    
    mean_signal = np.mean(filtered_signals, axis=0, dtype=np.float64)
    #mean_signal = filtered_signals[5]
    maxFreq, percentage = analyse_pca(mean_signal, fs=fps, draw=False)

    bpm = maxFreq * 60

    if show:
        global ax1, ax2
        ax1.cla()
        ax2.cla()
        analyse_pca(mean_signal, fs=fps, draw=True)
        fig.canvas.draw()

    return bpm


def analyse_pca(signal_data, fs=30, draw=False):
    
    # number of signal points
    N = len(signal_data)
    # sample spacing
    T = 1.0 / fs

    # Get fft
    spectrum = np.abs(fft(signal_data))
    spectrum *= spectrum
    xf = fftfreq(N, T)

    # Get maximum ffts index from second half
    #maxInd = np.argmax(spectrum[:int(len(spectrum)/2)+1])
    maxInd = np.argmax(spectrum)
    maxFreqPow = spectrum[maxInd]
    maxFreq = np.abs(xf[maxInd])

    total_power = np.sum(spectrum)
    # Get max frequencies power percentage in total power
    percentage = maxFreqPow / total_power
    
    if draw:
        global fig, ax1, ax2
        t = np.linspace(0.0, T*N, N)
        #fig, (ax1, ax2) = plt.subplots(2, 1)

        ax1.set_title('Signal data')
        ax1.plot(t, signal_data)
        #ax1.plot(peaks/fps, signal_data[peaks], "x")
        #ax1.plot(np.zeros_like(t/fps), "--", color="gray")
        ax1.set(xlabel='Time', ylabel='Pixel movement')
        ax1.grid()

        ax2.plot(xf, 1.0/N * spectrum)
        ax2.set_title('FFT')
        ax2.axvline(maxFreq, color='red')
        ax2.grid()
        ax2.set(xlabel='Freq', ylabel='')

        #print("Max power Freq {} % {} BPM:{}".format(maxFreq, percentage, bpm))

    return maxFreq, percentage


def do_pca(filtered_signals, fps, show=True):
    if len(filtered_signals) < 5:
        return 0
    
    pca = PCA(n_components=5)
    pca_result = pca.fit_transform(filtered_signals.T).T

    max_ratios = []
    max_freqs = []
    for i, signal_data in enumerate(pca_result):
        maxFreq, percentage = analyse_pca(signal_data, fs=fps, draw=False)
        max_ratios.append(percentage)
        max_freqs.append(maxFreq)

    # Find most sure freq out of pcas
    idx = np.argmax(max_ratios)
    last_pca = pca_result[idx]

    bpm = max_freqs[idx]*60

	
    if show:
        global ax1, ax2
        ax1.cla()
        ax2.cla()
        analyse_pca(last_pca, fs=fps, draw=True)
        fig.canvas.draw()

    return bpm



if __name__ == "__main__":

    #capture = cv2.VideoCapture('./data/face_videos/sitting2.avi')
    capture = cv2.VideoCapture(0)
    fps = int(capture.get(cv2.CAP_PROP_FPS))
    print('fps', fps)

    gray_frames = [] #0 is newest -1 is oldest
    bpm_list = [] #0 is newest -1 is oldest
    frame_c = 0

    # face = FacePoints()
    # tracking = TrackPoints(max_trace_history=300, max_trace_num=60)
    #face = FacePoints(dedector_type='face_shape')
    face = FacePoints(dedector_type='haar')
    tracking = TrackPoints(face_dedector=face, max_trace_history=180)

    # Create some random colors
    color = np.random.randint(0,255,(100,3))


    fig, (ax1, ax2) = plt.subplots(2, 1)
    fig.show()


    while capture.isOpened():
        # getting a frame
        ret, frame = capture.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        vis = frame.copy()

        gray_frames.insert(0, gray)


        # Wait 10 frames before selecting points
        if frame_c >= 3:
            gray_frames.pop()

            tracking.track_points(gray_frames[1], gray_frames[0])
            nextPts = tracking.get_current_points()

            # Draw points
            for i, new in enumerate(nextPts):
                a,b = new.ravel()
                vis = cv2.circle(vis,(a,b),5,color[i%100].tolist(),-1)

            # Draw Tracks
            cv2.polylines(vis, [np.int32(tr) for tr in tracking.traces], False, (0, 255, 0))



            # Calculate distance travalled by tracks
            trace_max_len = max( [len(trace) for trace in tracking.traces] )

            draw_str(vis, (20, 100), 'trace lenght: %d' % trace_max_len)


            if trace_max_len > 3*fps:
                #diff = get_diffs(tracking.traces, fps)
                traces = get_y(tracking.traces)
                filtered_signals = filter_out(traces, fps, low_c=0.75, high_c=3)
                bpm = do_pca(filtered_signals, fps)
                #bpm =  get_mean(filtered_signals, fps) # For face_shape

                bpm_list.insert(0, bpm)

                if len(bpm_list) > 10:
                    bpm_list.pop()

                    mean_bpm = sum(bpm_list) / len(bpm_list) 

                    draw_str(vis, (20, 20), 'bpm: %d' % mean_bpm)


        # Show
        cv2.imshow('Signal Process', vis)

        if cv2.waitKey( int(1) ) == 27:
            break

        frame_c += 1

    capture.release()
    cv2.destroyAllWindows()