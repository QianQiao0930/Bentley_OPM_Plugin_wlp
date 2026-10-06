"""逐阶段日志：窗口回调、控制台、即时落盘，保留异常堆栈。"""
import datetime
import os
import tempfile
import traceback
from contextlib import contextmanager

class GenerationLog:
    def __init__(self, sink=None, directory=None):
        self.sink = sink
        self.current_stage = '初始化'
        self.failed_stage = None
        self.lines = []
        folder = directory or os.path.join(os.path.dirname(__file__), 'logs')
        name = 'spiral_%s_%s.log' % (datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'), os.getpid())
        try:
            os.makedirs(folder, exist_ok=True)
            self.path = os.path.join(folder, name)
            self.file = open(self.path, 'w', encoding='utf-8-sig')
        except OSError:
            self.path = os.path.join(tempfile.gettempdir(), name)
            self.file = open(self.path, 'w', encoding='utf-8-sig')
        self.write('INFO', '日志文件：'+self.path)
    def write(self, level, message):
        text = '[%s] [%s] [%s] %s' % (datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3], level, self.current_stage, message)
        self.lines.append(text)
        self.file.write(text+'\n')
        self.file.flush()
        if self.sink:
            try:
                self.sink(text)
            except Exception:
                # 窗口已关闭时仍继续文件日志，不写系统控制台。
                self.sink = None
    @contextmanager
    def stage(self, name):
        previous = self.current_stage
        self.current_stage = name
        self.write('INFO', '开始')
        try:
            yield
        except Exception:
            if self.failed_stage is None:
                self.failed_stage = name
                self.write('ERROR', traceback.format_exc())
            raise
        else:
            self.write('INFO', '完成')
        finally:
            self.current_stage = previous
    def close(self):
        if not self.file.closed:
            self.file.close()
