"""应用上下文：把配置、i18n、信号总线、API 客户端与各服务统一挂在这里。"""
from .config import Settings
from .i18n import I18n
from .signals import SignalBus
from services.api_client import BlackboardAPI
from services.downloader import DownloadService


class AppContext:
    def __init__(self):
        self.settings = Settings()
        self.i18n = I18n(self.settings.get("lang", "zh"))
        self.signals = SignalBus()
        self.api = BlackboardAPI(log_cb=self.log)
        self.downloader = DownloadService(self.api)
        self.courses = {}
        self.current_course_id = ""
        self.current_course_name = ""
        # 每切换一次账号加 1。后台线程开始时记下它，回来时不一致就说明
        # 结果属于上一个账号，直接丢掉。
        self.account_epoch = 0

    def tr(self, key, *args):
        return self.i18n.tr(key, *args)

    def log(self, *args):
        text = " ".join(map(str, args))
        legacy_prefix = "[测验识别]"
        if text.startswith(legacy_prefix):
            text = f"[{self.tr('tab_quiz')}]" + text[len(legacy_prefix):]
        self.signals.log.emit(text)
