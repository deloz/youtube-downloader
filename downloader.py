import yt_dlp
import subprocess
import re
import os
import platform
import winreg
import urllib.request
import zipfile
import shutil
import time
import requests
import string

def get_available_formats(url, proxy=None):
    """ 获取所有可用格式 """
    ydl_opts = {
        'listformats': True,  # 列出所有可用格式
        'proxy': proxy,  # 设置代理
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get('formats', [])
    
    return formats, info_dict

def select_best_formats(formats):
    """ 选择最佳视频和音频格式 """
    best_video = None
    best_audio = None

    # 选择ID数字最大的视频格式
    for fmt in formats:
        # 确保是视频流（有视频编码且不是纯音频）
        if fmt.get('vcodec') and fmt['vcodec'] != 'none':
            try:
                # 尝试将format_id转换为整数
                format_id = int(fmt.get('format_id', '0'))
                if best_video is None or format_id > int(best_video.get('format_id', '0')):
                    best_video = fmt
            except ValueError:
                continue

    # 选择ID数字最大的音频格式
    for fmt in formats:
        # 确保是音频流（有音频编码且不是纯视频）
        if fmt.get('acodec') and fmt['acodec'] != 'none':
            try:
                # 尝试将format_id转换为整数
                format_id = int(fmt.get('format_id', '0'))
                if best_audio is None or format_id > int(best_audio.get('format_id', '0')):
                    best_audio = fmt
            except ValueError:
                continue

    return best_video, best_audio

def sanitize_filename(filename):
    """清理文件名，移除非法字符"""
    # 保留英文字母、数字、中文字符和一些基本符号，替换其他字符为下划线
    valid_chars = f'-_.() {string.ascii_letters}{string.digits}，。：！？'
    sanitized = ''.join(c if c in valid_chars else '_' for c in filename)
    # 移除可能导致问题的前导和尾随空格与点号
    sanitized = sanitized.strip('. ')
    # 如果文件名变成空字符串，使用默认名称
    if not sanitized:
        sanitized = "video"
    return sanitized

def download_with_progress(url, best_video, best_audio, video_title=None, proxy=None):
    """ 下载视频并显示进度 """
    # 创建下载目录
    download_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(download_dir, exist_ok=True)
    
    # 处理文件名
    if video_title:
        # 清理文件名中的非法字符
        safe_title = sanitize_filename(video_title)
        output_filename = os.path.join(download_dir, f"{safe_title}.mp4")
    else:
        output_filename = os.path.join(download_dir, "downloaded_video.mp4")
    
    # 根据实际格式设置正确的扩展名
    video_ext = best_video.get('ext', 'mp4')
    audio_ext = best_audio.get('ext', 'webm')
    
    video_filename = os.path.join(download_dir, f"temp_video_{best_video['format_id']}.{video_ext}")
    audio_filename = os.path.join(download_dir, f"temp_audio_{best_audio['format_id']}.{audio_ext}")
    
    try:
        # 下载视频流
        video_opts = {
            'format': best_video['format_id'],
            'outtmpl': video_filename,
            'proxy': proxy,
            'progress_hooks': [download_progress_hook],
        }
        print("\n正在下载视频流...")
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            ydl.download([url])
        
        # 下载音频流
        audio_opts = {
            'format': best_audio['format_id'],
            'outtmpl': audio_filename,
            'proxy': proxy,
            'progress_hooks': [download_progress_hook],
        }
        print("\n正在下载音频流...")
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        
        # 使用 ffmpeg 合并视频和音频，完全保留原始编码
        print("\n正在合并视频和音频...")
        print(f"输出文件: {output_filename}")
        ffmpeg_process = subprocess.Popen([
            'ffmpeg',
            '-i', video_filename,
            '-i', audio_filename,
            '-c:v', 'copy',           # 复制视频流，不重新编码
            '-c:a', 'aac',            # 将音频转换为AAC编码（MP4容器兼容）
            '-b:a', '192k',           # 设置音频比特率
            '-map', '0:v:0',          # 选择第一个文件的视频流
            '-map', '1:a:0',          # 选择第二个文件的音频流
            '-movflags', '+faststart', # 优化MP4文件结构
            output_filename
        ])
        ffmpeg_process.wait()  # 等待进程完成
        
        # 在删除文件前先等待一小段时间
        time.sleep(1)  # 给系统一些时间完全释放文件句柄
        
        # 清理临时文件的部分
        for temp_file in [video_filename, audio_filename]:
            if os.path.exists(temp_file):
                max_retries = 5  # 增加重试次数
                retry_delay = 1  # 减少每次重试的等待时间
                for attempt in range(max_retries):
                    try:
                        os.close(os.open(temp_file, os.O_RDONLY))  # 确保文件句柄被关闭
                        os.remove(temp_file)
                        break
                    except OSError as e:
                        if attempt == max_retries - 1:  # 最后一次尝试
                            print(f"警告：无法删除临时文件 {temp_file}: {e}")
                        else:
                            time.sleep(retry_delay)
                            continue
        return True, output_filename
        
    except Exception as e:
        print(f"\n下载或合并出错: {str(e)}")
        return False, None

def get_video_properties(file_path):
    """ 获取视频属性 """

    try:
        video_info = subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate',
            '-of', 'default=noprint_wrappers=1', file_path
        ]).decode('utf-8').strip()

        audio_info = subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'a:0',
            '-show_entries', 'stream=sample_rate,channels,bit_rate',
            '-of', 'default=noprint_wrappers=1', file_path
        ]).decode('utf-8').strip()

        return video_info, audio_info
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while getting video properties: {e}")
        return None, None

def compare_formats(downloaded_video_info, downloaded_audio_info, best_video, best_audio):
    """ 对比视频和音频格式 """

    video_match = False
    audio_match = False

    # 解析ffprobe的输出
    video_width = int(re.search(r'width=(\d+)', downloaded_video_info).group(1))
    video_height = int(re.search(r'height=(\d+)', downloaded_video_info).group(1))
    
    audio_sample_rate = int(re.search(r'sample_rate=(\d+)', downloaded_audio_info).group(1))
    audio_channels = int(re.search(r'channels=(\d+)', downloaded_audio_info).group(1))
    
    # 对比视频格式
    if best_video and (best_video.get('width') == video_width and best_video.get('height') == video_height):
        video_match = True
        print(f"Matching video format found: {best_video}")

    # 对比音频格式
    if best_audio and (best_audio.get('asr') == audio_sample_rate and best_audio.get('audio_channels') == audio_channels):
        audio_match = True
        print(f"Matching audio format found: {best_audio}")
    
    return video_match, audio_match

def extract_video_id(url):
    """ 从YouTube URL中提取视频ID """
    youtube_regex = (
        r'(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|user\/\w+\/|playlist\?list=)|'
        r'youtu\.be\/)'
        r'([\w-]{11})'
    )
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None

def is_youtube_url(url):
    """ 检查URL是否为有效的YouTube网址 """
    # 基本URL格式验证
    youtube_regex = (
        r'^(?:https?:\/\/)?(?:www\.)?'
        r'(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|user\/\w+\/|playlist\?list=)|'
        r'youtu\.be\/)'
        r'([\w-]{11})'  # 视频ID格式
    )
    
    if not re.match(youtube_regex, url):
        return False
    
    # 提取视频ID并验证
    video_id = extract_video_id(url)
    return video_id is not None

def get_youtube_url():
    """ 获取YouTube视频URL """
    while True:
        url = input("请输入YouTube视频URL(输入q退出): ").strip()
        if url.lower() == 'q':
            print("程序退出...")
            exit(0)
        if url and is_youtube_url(url):
            video_id = extract_video_id(url)
            # 构建标准化的URL格式
            return f"https://www.youtube.com/watch?v={video_id}"
        print("请输入一个有效的YouTube视频URL。")

def get_windows_proxy():
    """获取Windows系统代理设置"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Internet Settings',
            0, 
            winreg.KEY_READ
        ) as key:
            proxy_enable = winreg.QueryValueEx(key, 'ProxyEnable')[0]
            if proxy_enable:
                proxy_server = winreg.QueryValueEx(key, 'ProxyServer')[0]
                # 修改：确保返回正确格式的代理地址
                if proxy_server and ':' in proxy_server:
                    if not proxy_server.startswith(('http://', 'https://')):
                        return f'http://{proxy_server}'
                    return proxy_server
    except (WindowsError, TypeError):
        pass
    return None

def get_system_proxy():
    """获取系统代理"""
    if platform.system() == 'Windows':
        return get_windows_proxy()
    else:
        http_proxy = os.environ.get('http_proxy')
        https_proxy = os.environ.get('https_proxy')
        return http_proxy or https_proxy

def get_proxy_config():
    """ 获取代理配置 """
    system_proxy = get_system_proxy()
    if system_proxy:
        print(f"检测到系统代理: {system_proxy}")
        while True:
            use_proxy = input("是否使用系统代理? (y/n): ").strip().lower()
            if use_proxy == 'y':
                return system_proxy
            elif use_proxy == 'n':
                break
            else:
                print("请输入 y 或 n")
    
    while True:
        use_proxy = input("是否手动设置代理? (y/n): ").strip().lower()
        if use_proxy == 'y':
            proxy = input("请输入代理地址: ").strip()
            return proxy
        elif use_proxy == 'n':
            break
        else:
            print("请输入 y 或 n")
    
    return None

def download_progress_hook(d):
    if d['status'] == 'downloading':
        total = d.get('total_bytes')
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed', 0)
        
        if total:
            percentage = (downloaded / total) * 100
            downloaded_mb = downloaded / 1024 / 1024
            total_mb = total / 1024 / 1024
            speed_kb = speed / 1024 if speed else 0
            print(f"\r下载进度: {percentage:.1f}% | "
                  f"已下载: {downloaded_mb:.2f}MB / {total_mb:.2f}MB | "
                  f"速度: {speed_kb:.2f}KB/s", end='')

def download_with_resume(url, file_path, proxy=None):
    """支持断点续传的下载函数"""
    try:
        # 设置请求头和代理
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        proxies = {'http': proxy, 'https': proxy} if proxy else None
        
        # 获取已下载文件的大小
        file_size = 0
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            headers['Range'] = f'bytes={file_size}-'

        # 发送请求
        response = requests.get(url, headers=headers, proxies=proxies, stream=True)
        total_size = int(response.headers.get('content-length', 0)) + file_size
        
        mode = 'ab' if file_size > 0 else 'wb'
        print(f"\n继续从 {file_size/(1024*1024):.1f}MB 处开始下载...") if file_size > 0 else print("\n开始下载...")
        
        with open(file_path, mode) as f:
            downloaded = file_size
            chunk_size = 8192
            last_print_time = time.time()
            last_downloaded = downloaded
            
            for chunk in response.iter_content(chunk_size=chunk_size):
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                
                # 每秒更新一次下载进度
                current_time = time.time()
                if current_time - last_print_time >= 1.0:
                    speed = (downloaded - last_downloaded) / (current_time - last_print_time)
                    speed_text = f"{speed/1024/1024:.2f}MB/s"
                    
                    if total_size > 0:
                        percent = downloaded * 100 / total_size
                        print(f"\r下载进度: {percent:.1f}% | "
                              f"已下载: {downloaded/(1024*1024):.1f}MB / "
                              f"{total_size/(1024*1024):.1f}MB | "
                              f"速度: {speed_text}", end='')
                    else:
                        print(f"\r已下载: {downloaded/(1024*1024):.1f}MB | "
                              f"速度: {speed_text}", end='')
                    
                    last_print_time = current_time
                    last_downloaded = downloaded

        print("\n下载完成!")
        return True
            
    except requests.exceptions.RequestException as e:
        print(f"\n下载出错: {str(e)}")
        return False
    except Exception as e:
        print(f"\n发生未知错误: {str(e)}")
        return False

def download_and_install_ffmpeg(proxy=None):
    """下载并安装 FFmpeg 到当前目录"""
    if platform.system() != 'Windows':
        print("自动安装只支持 Windows 系统")
        return False
        
    temp_dir = None
    try:
        print("\n正在下载 FFmpeg...")
        temp_dir = os.path.join(os.getcwd(), 'temp_ffmpeg')
        os.makedirs(temp_dir, exist_ok=True)
        
        zip_path = os.path.join(temp_dir, "ffmpeg.zip")
        extract_path = os.path.join(temp_dir, "ffmpeg")
        
        # FFmpeg 下载链接
        download_urls = [
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
        ]
        
        # 尝试所有下载链接
        download_success = False
        for url in download_urls:
            print(f"\n尝试从 {url} 下载...")
            max_retries = 300
            for retry in range(max_retries):
                try:
                    if download_with_resume(url, zip_path, proxy):
                        # 验证下载的文件
                        if os.path.exists(zip_path) and zipfile.is_zipfile(zip_path):
                            download_success = True
                            break
                        else:
                            print(f"\n下载的文件无效,正在重试({retry + 1}/{max_retries})...")
                            if os.path.exists(zip_path):
                                os.remove(zip_path)
                except Exception as e:
                    print(f"\n下载出错: {str(e)}")
                    if retry < max_retries - 1:
                        print(f"等待 5 秒后重试({retry + 1}/{max_retries})...")
                        time.sleep(5)
                    continue
            
            if download_success:
                break
                
        if not download_success:
            print("\n所有下载地址均失败，请稍后重试或手动安装")
            return False
            
        # 解压后只复制需要的文件到当前目录
        print("正在解压并复制必要文件...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        ffmpeg_dirs = [d for d in os.listdir(extract_path) if 'ffmpeg' in d.lower()]
        if not ffmpeg_dirs:
            print("无法找到 FFmpeg 目录")
            return False
            
        bin_path = os.path.join(extract_path, ffmpeg_dirs[0], "bin")
        
        # 复制必要的可执行文件到当前目录
        for file in ['ffmpeg.exe', 'ffprobe.exe']:
            src = os.path.join(bin_path, file)
            dst = os.path.join(os.getcwd(), file)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                
        print("FFmpeg 文件已复制到当前目录！")
        return True
        
    except Exception as e:
        print(f"安装 FFmpeg 时出错: {str(e)}")
        return False
    finally:
        # 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"清理临时文件时出错: {str(e)}")

def check_ffmpeg(proxy=None):
    """ 检查当前目录或系统是否安装了 ffmpeg """
    current_dir = os.getcwd()
    ffmpeg_path = os.path.join(current_dir, 'ffmpeg.exe')
    ffprobe_path = os.path.join(current_dir, 'ffprobe.exe')
    
    if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
        return True
        
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        print("\nFFmpeg 未安装！")
        if platform.system() == 'Windows':
            print("\n是否要下载 FFmpeg 到当前目录？(y/n): ", end='')
            if input().strip().lower() == 'y':
                return download_and_install_ffmpeg(proxy)
            else:
                print("\n请手动下载 FFmpeg:")
                print("1. 访问 https://github.com/BtbN/FFmpeg-Builds/releases")
                print("2. 下载 ffmpeg-master-latest-win64-gpl.zip")
                print("3. 解压文件")
                print("4. 将 ffmpeg.exe 和 ffprobe.exe 复制到当前目录")
        else:
            print("请使用包管理器安装 FFmpeg:")
            print("Ubuntu/Debian: sudo apt-get install ffmpeg")
            print("macOS: brew install ffmpeg")
        return False

def main():
    try:
        print("\nYouTube视频下载器启动...")
        print("="*50 + "\n")
        
        # 先获取代理设置
        proxy = get_proxy_config()
        
        # 检查 ffmpeg 是否安装，传入代理参数
        if not check_ffmpeg(proxy):
            print("\n请安装 FFmpeg 后重试")
            return
            
        video_url = get_youtube_url()
        
        print("\n获取视频信息中...")
        available_formats, info_dict = get_available_formats(video_url, proxy)
        
        # 获取视频标题
        video_title = info_dict.get('title', 'downloaded_video')
        print(f"视频标题: {video_title}")
        
        best_video, best_audio = select_best_formats(available_formats)
        if not best_video or not best_audio:
            print("无法获取最佳视频或音频格式")
            return
            
        download_success, output_file = download_with_progress(video_url, best_video, best_audio, video_title, proxy)
        if download_success:
            print("\n\n下载完成!")
            print(f"文件保存在: {output_file}")
            
            video_info, audio_info = get_video_properties(output_file)
            if video_info and audio_info:
                video_match, audio_match = compare_formats(video_info, audio_info, best_video, best_audio)
                if video_match and audio_match:
                    print("视频和音频格式验证通过")
                else:
                    print("警告:下载的视频或音频格式与预期不符")
        
    except KeyboardInterrupt:
        print("\n\n用户取消下载")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")

if __name__ == "__main__":
    main()
