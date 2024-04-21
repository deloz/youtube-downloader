import subprocess
import os
import winreg

def get_windows_proxy():
    try:
        # 打开注册表键
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Internet Settings')

        # 读取代理设置
        proxy_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
        if proxy_enable == 1:
            proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
            return proxy_server
    except FileNotFoundError:
        print("未找到Windows代理设置")
    except Exception as e:
        print("获取Windows代理设置失败:", e)
    finally:
        winreg.CloseKey(key)

    return None

def download_video(url):
    # 获取系统代理设置
    proxy_server = get_windows_proxy()

    # 设置环境变量
    if proxy_server:
        os.environ['HTTP_PROXY'] = proxy_server
        os.environ['HTTPS_PROXY'] = proxy_server

    # 构建下载命令
    command = ['youtubedr', '--log-level', 'debug', 'download', '-q', 'hd', url]

    # 执行下载命令
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 逐行读取命令输出
    for line in process.stdout:
        print(line.strip())

    # 等待命令执行结束
    process.wait()

    # 检查是否出错
    if process.returncode != 0:
        print("下载出错:", process.stderr.read())
    else:
        print("下载完成")

        # 删除临时文件
        delete_temp_files()

def delete_temp_files():
    # 检查当前目录下的所有文件
    current_dir = os.getcwd()
    for filename in os.listdir(current_dir):
        if filename.endswith(".m4v") or filename.endswith(".m4a"):
            file_path = os.path.join(current_dir, filename)
            try:
                # 删除文件
                os.remove(file_path)
                print(f"删除临时文件: {filename}")
            except Exception as e:
                print(f"删除文件 {filename} 出错:", e)

if __name__ == "__main__":
    video_url = input("请输入YouTube视频链接: ")
    download_video(video_url)
