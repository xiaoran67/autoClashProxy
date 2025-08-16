import configparser

config = configparser.ConfigParser()
config.read('config.ini')

class Config:
    @property
    def open_m3u_result(self):
        return config.getboolean("Settings", "open_m3u_result", fallback=True)

    @property
    def sort_timeout(self):
        return int(config.get("Settings", "sort_timeout", fallback=10))

    @property
    def open_filter_resolution(self):
        return config.getboolean("Settings", "open_filter_resolution", fallback=True)

    @property
    def min_resolution_value(self):
        return int(config.get("Settings", "min_resolution_value", fallback=0))

    @property
    def open_supply(self):
        return config.getboolean("Settings", "open_supply", fallback=True)

    @property
    def open_filter_speed(self):
        return config.getboolean("Settings", "open_filter_speed", fallback=True)

    @property
    def min_speed(self):
        return float(config.get("Settings", "min_speed", fallback=0))

    @property
    def cdn_url(self):
        return config.get("Settings", "cdn_url", fallback="")

config_instance = Config()