import sqlite3
import os
import re
from json import JSONDecodeError
from time import sleep, time, strftime, strptime
import traceback
from urllib.parse import urlencode

import pywinauto
import random
from pywinauto.keyboard import send_keys
from selenium import webdriver
from selenium.common import WebDriverException, JavascriptException, NoSuchWindowException
from selenium.webdriver import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver

from tqdm import tqdm
import requests
import selenium
import json
import logging
import pyperclip

proxy = {
    "https": "127.0.0.1:33210",
    "http": "127.0.0.1:33210"
}

header = {
    "Access-Control-Allow-Origin": "*",
    "Accept": """text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7""",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

download_dir = os.path.abspath(r'A:\downloads')


def reload_config():
    return json.load(open("./config.json", encoding="utf-8"), )


def logger_factory():
    log_file_name = "log.log"
    log_level = 'DEBUG'
    formatter = logging.Formatter('[%(asctime)s (in %(funcName)s:%(lineno)d)] %(levelname)s: %(message)s')
    
    _logger = logging.getLogger('updateSecurity')
    _logger.setLevel(log_level)
    
    handler_test = logging.FileHandler(log_file_name)  # stdout to file
    handler_test.setLevel(log_level)
    handler_test.setFormatter(formatter)
    _logger.addHandler(handler_test)
    
    handler_control = logging.StreamHandler()  # stdout to console
    handler_control.setLevel(log_level)
    handler_control.setFormatter(formatter)
    _logger.addHandler(handler_control)
    return _logger


logger = logger_factory()


def _prepare_driver(port):
    chrome_options = selenium.webdriver.ChromeOptions()
    # chrome_options.add_argument(r' --user-data-dir={}'.format("./ChromeUserData")) # chrome参数已经指定，此处不须指定。
    chrome_options.add_argument(' --ignore-certificate-errors')
    chrome_options.add_argument(' --auto-open-devtools-for-tabs')
    # chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])  # TEST
    
    # prefs = {'profile.default_content_settings.popups': 0,
    #          'download.default_directory': download_dir}
    # chrome_options.add_experimental_option('prefs', prefs)
    chrome_options.add_argument(' --download.default_directory={}'.format(download_dir))
    
    chrome_options.add_experimental_option('debuggerAddress', '127.0.0.1:{}'.format(port))
    
    # 需要开启这个选项才能在调试工具中获取到请求
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    # caps = {
    #     "browserName": "chrome",
    #     : # 开启日志性能监听
    # }
    # chrome_options.add_argument(' --ignore-ssl-errors')
    #     # 把允许提示这个弹窗关闭
    # chrome_options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
    
    # Can use this code alternatively
    # See: https://wenku.csdn.net/answer/1684537ca4b343f89129c0bae02da37c
    # ret = ucd.ChromeDriver(chromedriver_path"PATH_TO_CHROMEDRIVER")
    
    # if len(config['chrome_driver_dir']) > 0:
    #     ret = webdriver.Chrome(service=Service(config['chrome_driver_dir']), options=chrome_options)
    # else:
    #     ret = ucd.Chrome(options=chrome_options)
    ret = webdriver.Chrome(service=Service("./env/chromedriver.exe"),
                           options=chrome_options)

    try:
        ret.maximize_window()
    except WebDriverException:
        pass
    return ret


def prepare_driver(url_dict, port):
    ret = _prepare_driver(port)
    if type(url_dict) == str:
        ret.get(url_dict)
        return ret
    else:
        for url in url_dict.values():
            ret.get(url)
            ret.switch_to.new_window("tab")
    handles = ret.window_handles
    handle_dict = {}
    k = list(url_dict.keys())
    for i in range(len(url_dict.keys())):
        handle_dict[k[i]] = handles[i]
    
    return ret, handle_dict


def open_links(url_dict, driver):
    handle_dict = {}
    
    for url_name in url_dict.keys():
        driver.switch_to.new_window("tab")
        driver.get(url_dict[url_name])
        handle_dict[url_name] = driver.current_window_handle
    # handles = ret.window_handles
    #
    # k = list(url_list.keys())
    # for i in range(len(url_list.keys())):
    #     handle_dict[k[i]] = handles[i]
    
    return handle_dict


@DeprecationWarning
def prepare_one_page_driver(url):
    ret = _prepare_driver()
    ret.get(url)
    return ret


def select_pics_to_post(pic_path, table_name, number=1):
    with sqlite3.connect('log.db') as conn:
        cur = conn.cursor()
        cur.execute('''
            create table IF NOT EXISTS {} (
                id INTEGER primary key AUTOINCREMENT,
                filename_md5 text not null,
                reposted_date date
            );
        '''.format(table_name))
        conn.commit()

        r = ""
        filenames = []
        while True:
            r, d, filenames = random.choice(list(os.walk(pic_path)))
            try:
                filename = random.choice(filenames)
            except IndexError:
                print(filenames)
                continue
            c = cur.execute('''
                    select * from {} where filename_md5="{}" and reposted_date is not null
                '''.format(table_name, filename))
            if len(c.fetchall()) <= 0 and not (os.path.isdir(os.path.join(r, filename)) or filename == "text.json"):
                return r, filename


def insert_to_log(data, column_names, table_name):
    with sqlite3.connect('log.db') as conn:
        cur = conn.cursor()
        cur.execute('''
            insert into {} ({}, reposted_date) values ("{}", {})
        '''.format(table_name, column_names, data, time()))
        conn.commit()


def open_pics(pic_path, table_name, number=1, win_open=True):
    # TODO linux
    
    if number > 18:
        number = 18
    if number < 1:
        number = 1
    
    config_file = open('./config.json', encoding="utf-8")
    config = json.load(config_file)
    config_file.close()
    try:
        r = config["priority_folder"]
        f = config["priority_pics"]
        if len(r) > 0 and len(f) > 0:
            r, filenames = r, f
        else:
            r, filenames = select_pics_to_post(pic_path, table_name)
    except KeyError:
        r, filenames = select_pics_to_post(pic_path, table_name)
    
    # r, filenames = select_pics_to_post(pic_path, table_name)
    # filenames = random.sample(os.listdir(PIC_PATH), number)
    
    # filenames = list(map(lambda f: '"{}"'.format(f), filenames))
    # filenames = ' '.join(filenames)
        
    sleep(1)
    if win_open:
        windows_open_file(r, filenames)
    
    try:
        config = json.load(open(os.path.join(r, "text.json"), 'r', encoding="utf-8"))
    except (FileNotFoundError, JSONDecodeError):
        traceback.print_exc()
        return r, filenames, None
    
    return r, filenames, config


def windows_open_file(path, filenames):
    app = pywinauto.Desktop()
    dialog = app["打开"]
    sleep(1)
    dialog["Toolbar3"].click()
    sleep(1)
    send_keys(path)
    send_keys("{VK_RETURN}")
    # filenames = os.path.join(r, filenames)
    sleep(1)
    input_string = ""
    # if len(filenames > 1):
    #     input_string = " ".join('"{}"'.format(filenames)) + '\n'
    # else
    #     input_string = filenames[0] + '\n'
    
    dialog["文件名(&N):Edit"].type_keys(filenames, with_spaces=True)
    sleep(0.5)
    send_keys("{ENTER}")
    # dialog["打开(&O)"].click()
    sleep(5)


def send_emoji_keys(driver, element, text):
    pyperclip.copy(text)
    element.send_keys(Keys.CONTROL, 'v')
    sleep(0.5)
    
    return driver


def quote_to_unicode(string):
    ret = []
    for char in string:
        x = str(b"\u" + hex(ord(char))[2:].upper().encode())[3:-1]
        ret.append(x)
    return "".join(ret)


def javascript_force_click(driver, button):
    try:
        driver.execute_script("arguments[0].click();", button)
    except JavascriptException:
        traceback.print_exc()
        logger.error("Input element error, maybe it is a LIST run by find_elementS.")


def mouse_pointer_force_click(driver, element):
    actions = ActionChains(driver)
    actions.move_to_element(element)
    actions.click(element)
    actions.perform()


def truncate_title(string):
    return re.sub(r"【\S+】", "", string)[:20]


def purge_non_ascii(string):
    return ''.join([c if ord(c) < 128 else '' for c in string])


def convert_date_to_chinese(english_date):
    try:
        season_dict = {
            "Spring": "春季",
            "Summer": "夏季",
            "Autumn": "秋季",
            "Winter": "冬季",
        }
        season = None
        for k in season_dict:
            season = re.search(k, english_date)
            if season is not None:
                break
        
        quarter = re.search(r"Q(\d)", english_date)
        year = re.search(r"\d{4}", english_date)
        
        if season is not None:
            return "于{}年{}".format(year.group(), season_dict[season.group()])
        
        if quarter is not None:
            return "于{}年第{}季度".format(year.group(), quarter.group(1))
        try:
            return strftime("于%Y年%m月%d日", strptime(english_date, "%d %b %Y"))
        except ValueError:
            try:
                return strftime("于%Y年%m月", strptime(english_date, "%b %Y"))
            except ValueError:
                return "于{}年".format(year.group()) if year is not None else ""
    except ValueError:
        return ""


def save_pics_js(driver, url, save_file_name, ext_name=None):
    """
    :param ext_name:
    :param driver:
    :param url:
    :param save_path:
    :param save_file_name:
    :return:
    """
    
    SCRIPT = """function download(url, name) {
    fileAjax(url, function(xhr) {
        downloadFile(xhr.response, name)
    }, {
        responseType: 'blob'
    })
}

function fileAjax(url, callback, options) {
    let xhr = new XMLHttpRequest()
    xhr.open('get', url, true)
    if (options.responseType) {
        xhr.responseType = options.responseType
    }
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4 && xhr.status === 200) {
            callback(xhr)
        }
    }
    xhr.send()
}

function downloadFile(content, filename) {
    window.URL = window.URL || window.webkitURL
    let a = document.createElement('a')
    let blob = new Blob([content])
    let url = window.URL.createObjectURL(blob)
    a.href = url
    a.download = filename
    a.click()
    window.URL.revokeObjectURL(url)
}
download(arguments[0], arguments[1])
"""
    if ext_name is not None:
        filename = os.path.join('{}.{}'.format(save_file_name, ext_name))
    else:
        filename = save_file_name
    driver.execute_script(SCRIPT, url, filename)


def tqdm_download(url: str, filename: str, headers=None):
    if headers is None:
        headers = header
    try:
        resp = requests.get(url, stream=True, headers=headers, verify=False, proxies=proxy)
        total = int(resp.headers.get('content-length', 0))
        if total < 20:
            return False
        with open(filename, 'wb') as file, tqdm(
                desc=filename,
                total=total,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                leave=False
        ) as bar:
            for data in resp.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)
        return True
    except OSError:
        open(filename, 'wb').write(requests.get(url, headers=header, verify=False, proxies=proxy).content)


def filter_media_requests(requests):
    return filter(lambda e: e['message']['params']['response']['mimeType'] not in [
        'application/javascript', 'application/x-javascript',
        'application/json', 'application/font-woff', 'application/manifest+json',
        'text/css', 'text/html', 'text/javascript', 'application/font-woff',
        'image/svg+xml'
        # 'webp', 'image/png', 'image/gif', 'video/mp4'
        # 'image/jpeg', 'image/x-icon', 'application/octet-stream'
    ], filter_requests(requests))


def filter_requests(requests):
    return filter(lambda e1: (e1['message']['method'] == 'Network.responseReceived')
                  , map(lambda e0: json.loads(e0['message']), requests))


def refresh_cookies_expiry(driver, expiry_time=5000000000):
    try:
        cookies = list(driver.get_cookies())  # pickle?
        for cookie in cookies:
            cookie['expiry'] = expiry_time
            driver.delete_cookie(cookie['name'])
            driver.add_cookie(cookie)
    except NoSuchWindowException:
        traceback.print_exc()
        pass


def find_from_complicate_dict(dic, key):
    print()


def dict_generator(indict, pre=None):
    pre = pre[:] if pre else []
    if isinstance(indict, dict):
        for key, value in indict.items():
            if isinstance(value, dict):
                for d in dict_generator(value, pre + [key]):
                    yield d
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d in dict_generator(v, pre + [key]):
                        yield d
            else:
                yield pre + [key, value]
    else:
        yield pre + [indict]


def selenium_send_request(driver: WebDriver, url: object, params: object, headers: dict, method: object = 'POST') -> object:
    javascript_script = '''
        xmlhttp = new XMLHttpRequest();
        xmlhttp.open("{method}","{url}",false);
        {headers}
        {send}
    '''
    header_javascript = ''.join(map(lambda k: 'xmlhttp.setRequestHeader("{key}","{value}");'.format(key=k, value=headers[k]), headers))
    if len(params) == 0:
        send_javascript = 'xmlhttp.send(null);'
    else:
        send_javascript = """
            xmlhttp.send(new Blob({params})); 
        """.format(params=str(list(params)))
    return driver.execute_script(javascript_script.format(
        method=method, url=url, headers=header_javascript, send=send_javascript
    ))
