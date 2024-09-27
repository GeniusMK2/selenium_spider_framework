import traceback

import schedule
import importlib
import sys
import gc

from utils import _prepare_driver
from utils import *


config = reload_config()

detail_config = config['detail']

if len(sys.argv) > 1:
    driver = _prepare_driver(port=int(sys.argv[1]))
else:
    driver = _prepare_driver(port=22222)
modules = {}


def reload():
    global config
    config = reload_config()
    refresh_cookies_expiry(driver)
    gc.collect()
    for j in schedule.jobs:
        print((j.last_run, j.next_run))


reload()
schedule.every(10).minutes.do(lambda: reload())

for _n in os.listdir("./modules"):
    try:
        m = importlib.import_module(".".join(["modules", _n, "module"]))
        
        # modules[_name]['module'] = importlib.import_module(".module", ".".join(["modules", _name]))
        _module_name = m.module_name
        logger.debug(_module_name)
        if (_module_name in detail_config) and ('enabled' in detail_config[_module_name])\
                and detail_config[_module_name]['enabled']:
            modules[_module_name] = {}
            modules[_module_name]['module'] = m
            modules[_module_name]['urls'] = modules[_module_name]['module'].init_urls
            modules[_module_name]['handlers'] = open_links(modules[_module_name]['module'].init_urls, driver)
            # print(modules)
            
            if detail_config[_module_name]['test']:
                try:
                    modules[_module_name]['module'].operation(driver, modules[_module_name]['handlers'])
                except KeyError as e:
                    logger.error("CHECK MODULE {} FOR URLS!".format(_module_name))
                    raise e
            for t in detail_config[_module_name]['times']:
                schedule.every().day.at(t).do(modules[_module_name]['module'].operation, driver, modules[_module_name]['handlers'])
        else:
            logger.info("Module {} is disabled.".format(_module_name))
            # modules[_name]['urls'] = []
            # modules[_name]['handlers'] = driver.window_handles[0]
    except (ModuleNotFoundError, KeyError):
        traceback.print_exc()

del _module_name


if __name__ == '__main__':
    while True:
        schedule.run_pending()
        
