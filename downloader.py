import yt_dlp
import subprocess
import re
import os
import platform
import winreg

def get_available_formats(url, proxy=None):
    """ 获取所有可用格式 """
    ydl_opts = {
        'listformats': True,  # 列出所有可用格式
        'proxy': proxy,  # 设置代理
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get('formats', [])
    
    return formats

def select_best_formats(formats):
    """ 选择最佳视频和音频格式 """

    best_video = None
    best_audio = None

    for fmt in formats:
        # 获取比特率并转换为浮点数
        tbr = fmt.get('tbr')
        if tbr is None:
            continue
        try:
            tbr = float(tbr)
        except ValueError:
            continue
        
        # 判断是否为视频格式
        if fmt.get('vcodec') and fmt['vcodec'] != 'none':
            if best_video is None or tbr > float(best_video.get('tbr', '0')):
                best_video = fmt
        
        # 判断是否为音频格式
        if fmt.get('acodec') and fmt['acodec'] != 'none' and fmt['height'] is None:
            if best_audio is None or tbr > float(best_audio.get('tbr', '0')):
                best_audio = fmt

    return best_video, best_audio

def download_best_video_and_audio(url, best_video, best_audio, output_filename='downloaded_video.mp4', proxy=None):
    """ 下载最佳视频和音频 """

    ydl_opts = {
        'format': f"{best_video['format_id']}+{best_audio['format_id']}",
        'merge_output_format': 'mp4',
        'outtmpl': output_filename,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'proxy': proxy,  # 设置代理
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

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


def is_youtube_url(url):
    """ 检查URL是否为有效的YouTube网址 """
    youtube_regex = (
        r'^(?:https?:\/\/)?(?:www\.)?'
        r'(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|user\/\w+\/|playlist\?list=)|'
        r'youtu\.be\/)'
        r'([\w-]{11})$'
    )
    return re.match(youtube_regex, url) is not None

def get_youtube_url():
    """ 获取YouTube视频URL """

    while True:
        url = input("请输入YouTube视频URL(输入q退出): ").strip()
        if url.lower() == 'q':
            print("程序退出...")
            exit(0)
        if url and is_youtube_url(url):
            return url
        print("请输入一个有效的YouTube视频URL。")

def get_windows_proxy():
    """获取Windows系统代理设置"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
        ) as key:
            proxy_enable = winreg.QueryValueEx(key, 'ProxyEnable')[0]
            if proxy_enable:
                proxy_server = winreg.QueryValueEx(key, 'ProxyServer')[0]
                if proxy_server and ':' in proxy_server:
                    return f'http://{proxy_server}'
    except WindowsError:
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
        use_proxy = input("是否使用系统代理? (y/n): ").strip().lower()
        if use_proxy == 'y':
            return system_proxy
    else:
        use_proxy = input("未检测到系统代理，是否手动设置代理? (y/n): ").strip().lower()
        if use_proxy == 'y':
            proxy = input("请输入代理地址: ").strip()
            return proxy
    return None

def download_with_progress(url, best_video, best_audio, output_filename='downloaded_video.mp4', proxy=None):
    """ 下载视频并显示进度 """

    ydl_opts = {
        'format': f"{best_video['format_id']}+{best_audio['format_id']}",
        'merge_output_format': 'mp4',
        'outtmpl': output_filename,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'proxy': proxy,
        'progress_hooks': [download_progress_hook],
        'retries': 10,
        'continuedl': True,  # 启用续传功能
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception as e:
            print(f"\n下载出错: {str(e)}")
            return False
    return True

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
        speed = d.get('speed', 0)
        
        if total:
            percentage = (downloaded / total) * 100
            downloaded_mb = downloaded / 1024 / 1024
            total_mb = total / 1024 / 1024
            speed_kb = speed / 1024 if speed else 0
            
            print(f"\r下载进度: {percentage:.1f}% | "
                  f"已下载: {downloaded_mb:.2f}MB / {total_mb:.2f}MB | "
                  f"速度: {speed_kb:.2f}KB/s", end='')

def main():
    try:
        print("\nYouTube视频下载器启动...")
        print("="*50 + "\n")
        
        video_url = get_youtube_url()
        proxy = get_proxy_config()
        
        print("\n获取视频信息中...")
        available_formats = get_available_formats(video_url, proxy)
        
        best_video, best_audio = select_best_formats(available_formats)
        if not best_video or not best_audio:
            print("无法获取最佳视频或音频格式")
            return
            
        output_file = 'downloaded_video.mp4'
        if download_with_progress(video_url, best_video, best_audio, output_file, proxy):
            print("\n\n下载完成!")
            
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
