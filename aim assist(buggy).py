import ctypes
import multiprocessing
import time
from multiprocessing import Process
import cv2
import pynput
from pynput.mouse import Button
from pynput.keyboard import Key, Listener
from win32gui import FindWindow, SetWindowPos, GetWindowText, GetForegroundWindow
from win32con import HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE
import winsound
from simple_pid import PID
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from functools import partial
import multiprocessing



def main():
    sqrt3 = np.sqrt(3)
    sqrt5 = np.sqrt(5)

    ads = 'ads'
    pidc = 'pidc'
    size = 'size'
    stop = 'stop'
    lock = 'lock'
    show = 'show'
    head = 'head'
    left = 'left'
    title = 'title'
    debug = 'debug'
    region = 'region'
    center = 'center'
    radius = 'radius'
    weights = 'weights'
    classes = 'classes'
    confidence = 'confidence'

    init = {
        title: 'Apex Legends',  # 可在后台运行 print(GetWindowText(GetForegroundWindow())) 来检测前台游戏窗体标题
        weights: '640s.engine',
        classes: 0,  # 要检测的标签的序号(标签序号从0开始), 多个时如右 [0, 1]
        confidence: 0.5,  # 置信度, 低于该值的认为是干扰
        size: 480,  # 截图的尺寸, 屏幕中心 size*size 大小
        radius: 100,  # 瞄准生效半径, 目标瞄点出现在以准星为圆心该值为半径的圆的范围内时才会锁定目标
        ads: 0.43,  # 移动倍数, 调整方式: 瞄准目标旁边并按住 Shift 键, 当准星移动到目标点的过程, 稳定精准快速不振荡时, 就找到了合适的 ADS 值
        center: None,  # 屏幕中心点
        region: None,  # 截图范围
        stop: False,  # 退出, End
        lock: False,  # 锁定, Shift, 按左键时不锁(否则扔雷时也会锁)
        show: False,  # 显示, Down
        head: False,  # 瞄头, Up
        pidc: False,  # 是否启用 PID Controller, 还未完善, Left
        left: True,  # 左键锁, Right, 按鼠标左键时锁
        debug: False,  # Debug 模式, 用来调试 PID 值
    }


    def wind_mouse(start_x, start_y, dest_x, dest_y, G_0=9, W_0=3, M_0=15, D_0=12, move_mouse=lambda x,y: None):
        current_x,current_y = start_x,start_y
        v_x = v_y = W_x = W_y = 0
        while (dist:=np.hypot(dest_x-start_x,dest_y-start_y)) >= 1:
            W_mag = min(W_0, dist)
            if dist >= D_0:
                W_x = W_x/sqrt3 + (2*np.random.random()-1)*W_mag/sqrt5
                W_y = W_y/sqrt3 + (2*np.random.random()-1)*W_mag/sqrt5
            else:
                W_x /= sqrt3
                W_y /= sqrt3
                if M_0 < 3:
                    M_0 = np.random.random()*3 + 3
                else:
                    M_0 /= sqrt5
            v_x += W_x + G_0*(dest_x-start_x)/dist
            v_y += W_y + G_0*(dest_y-start_y)/dist
            v_mag = np.hypot(v_x, v_y)
            if v_mag > M_0:
                v_clip = M_0/2 + np.random.random()*M_0/2
                v_x = (v_x_mag) * v_clip
                v_y = (v_y_mag) * v_clip
            start_x += v_x
            start_y += v_y
            move_x = int(np.round(start_x))
            move_y = int(np.round(start_y))
            if current_x != move_x or current_y != move_y:
                #This should wait for the mouse polling interval
                move_mouse(current_x:=move_x,current_y:=move_y)
        return current_x,current_y

    def game():
        return init[title] == GetWindowText(GetForegroundWindow())


    def mouse(data):

        def down(x, y, button, pressed):
            if not game():
                return
            if button == Button.left and data[left]:
                data[lock] = pressed
            elif button == pynput.mouse.Button.x2:
                if pressed:
                    data[left] = not data[left]
                    winsound.Beep(400, 200)
        with pynput.mouse.Listener(on_click=down) as m:
            m.join()


    def keyboard(data):

        def press(key):
            if not game():
                return
            if key == Key.shift:
                data[lock] = True

        def release(key):
            if key == Key.end:
                # 结束程序
                data[stop] = True
                winsound.Beep(400, 200)
                return False
            if not game():
                return
            if key == Key.shift:
                data[lock] = False
            elif key == Key.up:
                data[head] = not data[head]
                winsound.Beep(800 if data[head] else 400, 200)
            elif key == Key.down:
                data[show] = not data[show]
                winsound.Beep(800 if data[show] else 400, 200)
            elif key == Key.left:
                data[pidc] = not data[pidc]
                winsound.Beep(800 if data[pidc] else 400, 200)
            elif key == Key.right:
                data[left] = not data[left]
                winsound.Beep(800 if data[left] else 400, 200)
            elif key == Key.page_down:
                data[debug] = not data[debug]
                winsound.Beep(800 if data[debug] else 400, 200)

        with Listener(on_release=release, on_press=press) as k:
            k.join()


    def loop(data):

        from toolkit import Capturer, Detector, Predictor, Timer
        capturer = Capturer(data[title], data[region])
        detector = Detector(data[weights], data[classes])
        winsound.Beep(800, 200)

        try:
            import os
            root = os.path.abspath(os.path.dirname(__file__))
            driver = ctypes.CDLL(f'{root}/logitech.driver.dll')
            ok = driver.device_open() == 1
            if not ok:
                print('初始化失败, 未安装罗技驱动')
        except FileNotFoundError:
            print('初始化失败, 缺少文件')

        def move(x: int, y: int):
            if (x == 0) & (y == 0):
                return
            start_x, start_y = data[center]
            dest_x, dest_y = start_x + x, start_y + y
            wind_mouse(start_x, start_y, dest_x, dest_y, move_mouse=move_mouse)

        def inner(point):
            """
            判断该点是否在准星的瞄准范围内
            """
            a, b = data[center]
            x, y = point
            return (x - a) ** 2 + (y - b) ** 2 < data[radius] ** 2

        def follow(aims):
            """
            从 targets 里选目标瞄点距离准星最近的
            """
            if len(aims) == 0:
                return None

            # 瞄点调整
            targets = []
            for index, clazz, conf, sc, gc, sr, gr in aims:
                if conf < data[confidence]:  # 特意把置信度过滤放到这里(便于从图片中查看所有识别到的目标的置信度)
                    continue
                _, _, _, height = sr
                sx, sy = sc
                gx, gy = gc
                differ = (height // 7) if data[head] else (height // 3)
                newSc = sx, sy - height // 2 + differ  # 屏幕坐标系下各目标的瞄点坐标, 计算身体和头在方框中的大概位置来获得瞄点, 没有采用头标签的方式(感觉效果特别差)
                newGc = gx, gy - height // 2 + differ
                targets.append((index, clazz, conf, newSc, newGc, sr, gr))
            if len(targets) == 0:
                return None

            # 找到目标
            cx, cy = data[center]
            index = 0
            minimum = 0
            for i, item in enumerate(targets):
                index, clazz, conf, sc, gc, sr, gr = item
                sx, sy = sc
                distance = (sx - cx) ** 2 + (sy - cy) ** 2
                if minimum == 0:
                    index = i
                    minimum = distance
                else:
                    if distance < minimum:
                        index = i
                        minimum = distance
            return targets[index]

        text = 'Realtime Screen Capture Detect'
        pidx = PID(2, 0, 0.02, setpoint=0)
        counter = 0  # 用于还原 pidx的setpoint, 连续多次pidx(x)的值在某范围内, 则认为目标不动, 还原
        # pidx.output_limits = [-50, 50]
        pidy = PID(2, 0, 0.02, setpoint=0)
        times, targets, distances = [], [], []  # 用于绘图

        # 主循环
        while True:

            if data[stop]:
                break

            # 生产数据
            t1 = time.perf_counter_ns()
            img = capturer.grab()
            t2 = time.perf_counter_ns()
            aims, img = detector.detect(image=img, show=data[show])  # 目标检测, 得到截图坐标系内识别到的目标和标注好的图片(无需展示图片时img为none)
            t3 = time.perf_counter_ns()
            aims = detector.convert(aims=aims, region=data[region])  # 将截图坐标系转换为屏幕坐标系
            # print(f'{Timer.cost(t3 - t1)}, {Timer.cost(t2 - t1)}, {Timer.cost(t3 - t2)}')

            # 找到目标
            target = follow(aims)

            # 移动准星
            if data[lock] and target:
                index, clazz, conf, sc, gc, sr, gr = target
                if inner(sc):
                    cx, cy = data[center]
                    sx, sy = sc
                    x = sx - cx
                    y = sy - cy
                    if data[pidc]:
                        if data[debug]:  # 用于绘图
                            times.append(time.time())
                            targets.append(0)
                            distances.append(x)
                        px = -int(pidx(x))
                        if px > 20:
                            pidx.setpoint = -20
                        elif px < -20:
                            pidx.setpoint = 20
                        else:
                            counter += 1
                            if counter > 1:
                                pidx.setpoint = 0
                                counter = 0
                        py = -int(pidy(y))
                        move(px, py)
                        time.sleep(0.001)
                    else:
                        ax = int(x * data[ads])
                        ay = int(y * data[ads])
                        move(ax, ay)
            else:  # 用于绘图
                if data[debug] and len(times) != 0:
                    try:
                        plt.plot(times, targets, label='target')
                        plt.plot(times, distances, label='distance')
                        plt.legend()  # 图例
                        plt.xlabel('time')
                        plt.ylabel('distance')
                        times.clear()
                        targets.clear()
                        distances.clear()
                        matplotlib.use('TkAgg')  # TkAgg, module://backend_interagg
                        winsound.Beep(600, 200)
                        plt.show()
                    except:
                        pass

            # 显示检测
            if data[show] and img is not None:
                # 记录耗时
                cv2.putText(img, f'{Timer.cost(t3 - t1)}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 1)
                cv2.putText(img, f'{Timer.cost(t2 - t1)}', (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 1)
                cv2.putText(img, f'{Timer.cost(t3 - t2)}', (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 1)
                # 瞄点划线
                if target:
                    index, clazz, conf, sc, gc, sr, gr = target
                    cv2.circle(img, gc, 2, (0, 0, 0), 2)
                    r = data[size] // 2
                    cv2.line(img, gc, (r, r), (255, 255, 0), 2)
                # 展示图片
                cv2.namedWindow(text, cv2.WINDOW_AUTOSIZE)
                cv2.imshow(text, img)
                SetWindowPos(FindWindow(None, text), HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                cv2.waitKey(1)
            if not data[show]:
                cv2.destroyAllWindows()


    if __name__ == '__main__':
        multiprocessing.freeze_support()
        manager = multiprocessing.Manager()
        data = manager.dict()
        data.update(init)
        # 初始化数据
        from toolkit import Monitor
        data[center] = Monitor.resolution.center()
        c1, c2 = data[center]
        data[region] = c1 - data[size] // 2, c2 - data[size] // 2, data[size], data[size]
        # 创建进程
        pm = Process(target=mouse, args=(data,), name='Mouse')
        pk = Process(target=keyboard, args=(data,), name='Keyboard')
        pl = Process(target=loop, args=(data,), name='Loop')
        # 启动进程
        pm.start()
        pk.start()
        pl.start()
        pk.join()  # 不写 join 的话, 使用 dict 的地方就会报错 conn = self._tls.connection, AttributeError: 'ForkAwareLocal' object has no attribute 'connection'
        pm.terminate()  # 鼠标进程无法主动监听到终止信号, 所以需强制结束
    import tkinter as tk
    from tkinter import ttk

    def on_submit():
        init[title] = title_entry.get()
        init[weights] = weights_entry.get()
        init[classes] = int(classes_entry.get())
        init[confidence] = float(confidence_entry.get())
        init[size] = int(size_entry.get())
        init[radius] = int(radius_entry.get())
        init[ads] = float(ads_entry.get())

        # Start the program loop with the updated init values
        multiprocessing.Process(target=loop, args=(init,)).start()

    root = tk.Tk()
    root.title("Apex Legends Aimbot")

    frame = ttk.Frame(root, padding="10")
    frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    # Labels and Entry widgets for the various configuration options
    title_label = ttk.Label(frame, text="Title:")
    title_entry = ttk.Entry(frame, width=30)
    title_entry.insert(0, init[title])

    weights_label = ttk.Label(frame, text="Weights:")
    weights_entry = ttk.Entry(frame, width=30)
    weights_entry.insert(0, init[weights])

    classes_label = ttk.Label(frame, text="Classes:")
    classes_entry = ttk.Entry(frame, width=30)
    classes_entry.insert(0, init[classes])

    confidence_label = ttk.Label(frame, text="Confidence:")
    confidence_entry = ttk.Entry(frame, width=30)
    confidence_entry.insert(0, init[confidence])

    size_label = ttk.Label(frame, text="Size:")
    size_entry = ttk.Entry(frame, width=30)
    size_entry.insert(0, init[size])

    radius_label = ttk.Label(frame, text="Radius:")
    radius_entry = ttk.Entry(frame, width=30)
    radius_entry.insert(0, init[radius])

    ads_label = ttk.Label(frame, text="ADS:")
    ads_entry = ttk.Entry(frame, width=30)
    ads_entry.insert(0, init[ads])

    submit_button = ttk.Button(frame, text="Start", command=on_submit)

    # Grid layout for the widgets
    title_label.grid(row=0, column=0, sticky=tk.W)
    title_entry.grid(row=0, column=1, sticky=tk.W)
    weights_label.grid(row=1, column=0, sticky=tk.W)
    weights_entry.grid(row=1, column=1, sticky=tk.W)
    classes_label.grid(row=2, column=0, sticky=tk.W)
    classes_entry.grid(row=2, column=1, sticky=tk.W)
    confidence_label.grid(row=3, column=0, sticky=tk.W)
    confidence_entry.grid(row=3, column=1, sticky=tk.W)
    size_label.grid(row=4, column=0, sticky=tk.W)
    size_entry.grid(row=4, column=1, sticky=tk.W)
    radius_label.grid(row=5, column=0, sticky=tk.W)
    radius_entry.grid(row=5, column=1, sticky=tk.W)
    ads_label.grid(row=6, column=0, sticky=tk.W)
    ads_entry.grid(row=6, column=1, sticky=tk.W)
    submit_button.grid(row=7, column=1, sticky=tk.E)

    # Start the GUI event loop
    root.mainloop()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()