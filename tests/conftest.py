import os
import pytest
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def pytest_addoption(parser):
    """
    pytest钩子函数：添加自定义命令行选项
    用于支持多环境配置切换
    """
    parser.addoption(
        "--env",
        action="store",
        default="dev",
        choice=["dev", "test", "idc"],
        help="设置测试环境：dev（开发环境）、test（测试环境）、idc（生产环境）"
    )


@pytest.fixture(scope="session")
def env_config(request):
    """
    根据命令行参数加载不同环境配置
    """
    env = request.config.getoption("--env")
    configs = {
        "dev": {
            "base_url": "http://dev.bitjungle.cn/",
            "api_endpoint": "http://dev.bitjungle.cn/zhongkui/api"
        },
        "test": {
            "base_url": "http://test.bitjungle.cn/",
            "api_endpoint": "http://test.bitjungle.cn/zhongkui/api"
        },
        "idc": {
            "base_url": "http://idc.bitjungle.cn/",
            "api_endpoint": "http://idc.bitjungle.cn/zhongkui/api"
        }
    }
    print(f"\n当前测试环境：{env.upper()}环境")
    return configs[env]


@pytest.fixture(scope="session")
def browser(env_config):
    """
    浏览器实例
    特性：
    - 自动初始化Chrome浏览器
    - 默认隐式等待10秒
    - 自动关闭浏览器（测试结束后）
    - 集成环境配置
    """
    options = webdriver.ChromeOptions()

    # 生产环境使用无头模式
    if env_config['base_url'].startswith("http://idc"):
        options.add_argument("--headless=new")

    # 初始化浏览器实例
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)  # 全局隐式等待

    # 设置基础URL
    driver.base_url = env_config["base_url"]

    # 窗口最大化
    driver.maximize_window()

    yield driver  # 将控制权交给测试用例

    # 测试结束后自动清理
    driver.quit()


@pytest.fixture(scope="session")
def logged_in_browser(browser, env_config, request):
    """
    带登录状态的浏览器fixture（会话级）
    流程：
    1. 访问登录页面
    2. 等待二维码加载
    3. 人工扫码登录
    4. 验证登录状态
    5. 返回已登录的浏览器实例

    依赖项：
    - browser：基础浏览器实例
    - env_config：环境配置
    """

    print("\n[准备阶段] 开始处理扫码登录...")

    # 步骤1: 访问首页
    browser.get(env_config["base_url"])
    print("已访问首页，等待页面加载完成...")

    try:
        # 步骤2:点击登录按钮
        print("正在定位登录按钮...")
        login_button = WebDriverWait(browser, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "header-user-btn"))
        )
        login_button.click()

        # 步骤3: 等待二维码加载（显式等待）
        qr_element = WebDriverWait(browser, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "img[src*='showqrcode']"))
        )
        print("二维码已加载")

        # 步骤4: 人工扫码提示
        input("n 重要提示：请打开企业微信扫描屏幕上的二维码，登录成功后按回车键继续自动化测试...")

        # 步骤5: 验证登录成功
        print("验证登录状态...")
        WebDriverWait(browser, 10).until(
            lambda d: d.current_url.endswith("/dashboard")  # 登录后跳转验证
        )

        # 保存登录后的cookies(用于失败重试)
        request.config.cache.set("auth_cookies", browser.get_cookies())

    except TimeoutException as e:
        # 失败处理
        error_msg = "登录流程超时："
        if "header-user-btn" in str(e):
            error_msg += "登录按钮未在10秒内加载"
        elif "showqrcode" in str(e):
            error_msg += "二维码未在45秒内加载"
        else:
            error_msg += "扫码后未在30秒内跳转"

        # 自动截图
        browser.save_screenshot("login_failure.png")
        print(f"{error_msg}，已保存截图：login_failure.png")
        pytest.exit(error_msg)  # 终止测试执行

    print("扫码登录成功")
    return browser


@pytest.fixture(autouse=True)
def failure_screenshot(request, browser):
    """
    自动失败截图fixture（函数级）
    特性：
    - 每个测试用例自动生效（autouse=True）
    - 仅在用例失败时触发
    - 按时间戳生成唯一截图文件名
    """

    yield # 让出控制权给测试用例
    if request.node.rep_call.failed:
        # 生产时间戳
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # 创建截图目录
        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")

        # 保存截图
        case_name = request.node.name.replace("[", "_").replace("]", "_")
        filename = f"screenshots/failure_{case_name}_{timestamp}.png"
        browser.save_screenshot(filename)
        print(f"测试失败截图已保存：{filename}")


@pytest.fixture(scope="session")
def api_client(env_config):
    """
    API客户端fixture
    用于需要接口调用的测试场景
    返回预配置的requests Session对象
    """
    import requests
    session = requests.Session()

    # 配置基础URL和请求头
    session.base_url = env_config["api_endpoint"]
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "AutoTest/1.0"
    })

    return session




