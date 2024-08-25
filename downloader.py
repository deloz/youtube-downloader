import yt_dlp
import subprocess
import re
import math

def get_available_formats(url, proxy=None):
    ydl_opts = {
        'listformats': True,  # 列出所有可用格式
        'proxy': proxy,  # 设置代理
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        formats = info_dict.get('formats', [])
    
    return formats

def select_best_formats(formats):
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
    video_match = False
    audio_match = False

    # 解析ffprobe的输出
    video_width = int(re.search(r'width=(\d+)', downloaded_video_info).group(1))
    video_height = int(re.search(r'height=(\d+)', downloaded_video_info).group(1))
    video_frame_rate = re.search(r'r_frame_rate=(\d+/\d+)', downloaded_video_info).group(1)
    
    audio_sample_rate = int(re.search(r'sample_rate=(\d+)', downloaded_audio_info).group(1))
    audio_channels = int(re.search(r'channels=(\d+)', downloaded_audio_info).group(1))
    audio_bit_rate = int(re.search(r'bit_rate=(\d+)', downloaded_audio_info).group(1))
    
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
    while True:
        url = input("请输入YouTube视频的URL: ").strip()  # 去除前后空白字符
        if url and is_youtube_url(url):
            return url
        print("请输入一个有效的YouTube视频URL。")




def main():
    video_url = get_youtube_url()
    # 设置代理
    proxy = 'http://127.0.0.1:10809'
    
    print(f"你输入的URL是: {video_url}")
    print(f"使用代理: {proxy}")

    # 步骤1: 获取所有可用格式
    available_formats = get_available_formats(video_url, proxy)

    # 步骤2: 从可用格式中选择最好的视频和音频格式
    best_video, best_audio = select_best_formats(available_formats)
    print(f"Selected best video format: {best_video}")
    print(f"Selected best audio format: {best_audio}")

    # 步骤3: 下载并合并选定的视频和音频
    output_file = 'downloaded_video.mp4'
    download_best_video_and_audio(video_url, best_video, best_audio, output_file, proxy)

    # 步骤4: 获取已下载视频和音频的属性
    video_info, audio_info = get_video_properties(output_file)
    print("\nDownloaded Video Info:")
    print(video_info)
    print("\nDownloaded Audio Info:")
    print(audio_info)

    # 步骤5: 对比已下载文件的格式与选定的最佳格式
    video_match, audio_match = compare_formats(video_info, audio_info, best_video, best_audio)

    if video_match and audio_match:
        print("The downloaded video and audio match the selected best formats.")
    else:
        print("The downloaded video and/or audio do not match the selected best formats.")

if __name__ == "__main__":
    main()
