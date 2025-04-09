import yt_dlp
import subprocess
import re
import os
import platform
import winreg
import zipfile
import shutil
import time
import requests
import argparse
from pathlib import Path
import asyncio
import concurrent.futures
from typing import Dict, List, Tuple, Optional, Any, Union


async def get_available_formats(
    url: str, proxy: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """获取所有可用格式"""
    ydl_opts = {
        "listformats": True,  # 列出所有可用格式
        "proxy": proxy,  # 设置代理
    }

    loop = asyncio.get_event_loop()
    async with asyncio.Lock():
        info_dict = await loop.run_in_executor(
            None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False)
        )
        formats = info_dict.get("formats", [])

    return formats, info_dict


def select_best_formats(
    formats: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """选择最佳视频和音频格式"""
    best_video = None
    best_audio = None

    # 选择ID数字最大的视频格式
    for fmt in formats:
        # 确保是视频流（有视频编码且不是纯音频）
        if fmt.get("vcodec") and fmt["vcodec"] != "none":
            try:
                # 尝试将format_id转换为整数
                format_id = int(fmt.get("format_id", "0"))
                if best_video is None or format_id > int(
                    best_video.get("format_id", "0")
                ):
                    best_video = fmt
            except ValueError:
                continue

    # 选择ID数字最大的音频格式
    for fmt in formats:
        # 确保是音频流（有音频编码且不是纯视频）
        if fmt.get("acodec") and fmt["acodec"] != "none":
            try:
                # 尝试将format_id转换为整数
                format_id = int(fmt.get("format_id", "0"))
                if best_audio is None or format_id > int(
                    best_audio.get("format_id", "0")
                ):
                    best_audio = fmt
            except ValueError:
                continue

    return best_video, best_audio


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    path = Path(filename)
    stem = path.stem
    suffix = path.suffix

    # Windows保留文件名列表
    INVALID_NAMES = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }

    # 检查是否为Windows保留文件名
    base = stem.upper()
    if base in INVALID_NAMES:
        stem = f"_{stem}_"

    # 检查非法字符（Windows文件名不允许的字符）
    sanitized_stem = re.sub(r'[\\/:*?"<>|]', "_", stem)

    # 移除可能导致问题的前导和尾随空格与点号
    sanitized_stem = sanitized_stem.strip(". ")

    # 如果文件名变成空字符串，使用默认名称
    if not sanitized_stem:
        sanitized_stem = "video"

    # 组合处理后的文件名和原始后缀
    return sanitized_stem + suffix


def download_progress_hook(d: Dict[str, Any]) -> None:
    """下载进度回调函数"""
    if d["status"] == "downloading":
        total = d.get("total_bytes")
        downloaded = d.get("downloaded_bytes", 0)
        speed = d.get("speed", 0)

        if total:
            percentage = (downloaded / total) * 100
            downloaded_mb = downloaded / 1024 / 1024
            total_mb = total / 1024 / 1024
            speed_kb = speed / 1024 if speed else 0
            print(
                f"\r下载进度: {percentage:.1f}% | "
                f"已下载: {downloaded_mb:.2f}MB / {total_mb:.2f}MB | "
                f"速度: {speed_kb:.2f}KB/s",
                end="",
            )


async def download_audio(
    url: str,
    audio_format: Dict[str, Any],
    filename: Union[str, Path],
    proxy: Optional[str] = None,
    concurrent_fragments: int = 3,
) -> Tuple[bool, Optional[Union[str, Path]]]:
    """下载音频流"""
    try:
        audio_opts = {
            "format": audio_format["format_id"],
            "outtmpl": str(filename),
            "proxy": proxy,
            "concurrent_fragment_downloads": concurrent_fragments,  # 并行下载片段
            "progress_hooks": [download_progress_hook],
        }
        print("\n正在下载音频流...")

        loop = asyncio.get_event_loop()
        async with asyncio.Lock():
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(audio_opts).download([url])
            )
        return True, filename
    except Exception as e:
        print(f"\n下载音频出错: {str(e)}")
        return False, None


async def download_video(
    url: str,
    video_format: Dict[str, Any],
    filename: Union[str, Path],
    proxy: Optional[str] = None,
    concurrent_fragments: int = 3,
) -> Tuple[bool, Optional[Union[str, Path]]]:
    """下载视频流"""
    try:
        video_opts = {
            "format": video_format["format_id"],
            "outtmpl": str(filename),
            "proxy": proxy,
            "concurrent_fragment_downloads": concurrent_fragments,  # 并行下载片段
            "progress_hooks": [download_progress_hook],
        }
        print("\n正在下载视频流...")

        loop = asyncio.get_event_loop()
        async with asyncio.Lock():
            await loop.run_in_executor(
                None, lambda: yt_dlp.YoutubeDL(video_opts).download([url])
            )
        return True, filename
    except Exception as e:
        print(f"\n下载视频出错: {str(e)}")
        return False, None


async def merge_audio_video(
    video_file: Union[str, Path],
    audio_file: Union[str, Path],
    output_file: Union[str, Path],
) -> bool:
    """合并音频和视频"""
    try:
        print("\n正在合并视频和音频...")
        print(f"输出文件: {output_file}")

        loop = asyncio.get_event_loop()
        ffmpeg_process = await loop.run_in_executor(
            None,
            lambda: subprocess.Popen(
                [
                    "ffmpeg",
                    "-i",
                    str(video_file),
                    "-i",
                    str(audio_file),
                    "-c:v",
                    "copy",  # 复制视频流，不重新编码
                    "-c:a",
                    "aac",  # 将音频转换为AAC编码（MP4容器兼容）
                    "-b:a",
                    "192k",  # 设置音频比特率
                    "-map",
                    "0:v:0",  # 选择第一个文件的视频流
                    "-map",
                    "1:a:0",  # 选择第二个文件的音频流
                    "-movflags",
                    "+faststart",  # 优化MP4文件结构
                    str(output_file),
                ]
            ),
        )
        await loop.run_in_executor(None, ffmpeg_process.wait)  # 等待进程完成
        return True
    except Exception as e:
        print(f"\n合并出错: {str(e)}")
        return False


async def clean_temp_files(file_list: List[Union[str, Path]]) -> None:
    """清理临时文件"""
    # 在删除文件前先等待一小段时间
    await asyncio.sleep(1)  # 给系统一些时间完全释放文件句柄

    for temp_file in file_list:
        path_file = Path(temp_file)
        if path_file.exists():
            max_retries = 5  # 增加重试次数
            retry_delay = 1  # 减少每次重试的等待时间
            for attempt in range(max_retries):
                try:
                    # 使用pathlib的unlink方法删除文件
                    path_file.unlink()
                    break
                except OSError as e:
                    if attempt == max_retries - 1:  # 最后一次尝试
                        print(f"警告：无法删除临时文件 {temp_file}: {e}")
                    else:
                        await asyncio.sleep(retry_delay)
                        continue


async def download_with_progress(
    url: str,
    best_video: Optional[Dict[str, Any]],
    best_audio: Dict[str, Any],
    video_title: Optional[str] = None,
    proxy: Optional[str] = None,
    only_audio: bool = False,
    playlist_dir: Optional[str] = None,
    concurrent_fragments: int = 3,
) -> Tuple[bool, Optional[str]]:
    """下载视频并显示进度"""
    # 创建下载目录
    download_dir = Path.cwd() / "downloads"
    if playlist_dir:
        download_dir = download_dir / playlist_dir
    download_dir.mkdir(exist_ok=True, parents=True)

    # 从URL提取视频ID，用于临时文件命名
    video_id = extract_video_id(url) or "unknown"

    # 处理文件名
    if video_title:
        # 清理文件名中的非法字符
        safe_title = sanitize_filename(video_title)
    else:
        safe_title = "downloaded_video"

    # 使用视频ID命名临时文件
    # 根据实际格式设置正确的扩展名
    audio_ext = best_audio.get("ext", "webm")
    audio_filename = download_dir / f"{video_id}_{best_audio['format_id']}.{audio_ext}"

    # 如果只下载音频
    if only_audio:
        success, audio_file = await download_audio(
            url, best_audio, audio_filename, proxy, concurrent_fragments
        )
        if success:
            # 设置输出文件名（最终文件仍使用标题，包括前缀）
            output_filename = download_dir / f"{safe_title}.mp3"

            # 转换为MP3格式
            print("\n正在转换为MP3格式...")
            loop = asyncio.get_event_loop()
            ffmpeg_process = await loop.run_in_executor(
                None,
                lambda: subprocess.Popen(
                    [
                        "ffmpeg",
                        "-i",
                        str(audio_file),
                        "-vn",  # 移除视频流
                        "-c:a",
                        "libmp3lame",  # MP3编码器
                        "-q:a",
                        "2",  # 音频质量设置 (0-9, 0是最高质量)
                        str(output_filename),
                    ]
                ),
            )
            await loop.run_in_executor(None, ffmpeg_process.wait)

            # 清理临时文件
            await clean_temp_files([audio_file])
            return True, str(output_filename)
        return False, None

    # 下载视频和音频
    video_ext = best_video.get("ext", "mp4")
    video_filename = download_dir / f"{video_id}_{best_video['format_id']}.{video_ext}"
    # 保留前缀的输出文件名
    output_filename = download_dir / f"{safe_title}.mp4"

    # 下载视频
    video_success, video_file = await download_video(
        url, best_video, video_filename, proxy, concurrent_fragments
    )
    if not video_success:
        return False, None

    # 下载音频
    audio_success, audio_file = await download_audio(
        url, best_audio, audio_filename, proxy, concurrent_fragments
    )
    if not audio_success:
        # 清理已下载的视频文件
        await clean_temp_files([video_file])
        return False, None

    # 合并视频和音频
    if await merge_audio_video(video_file, audio_file, output_filename):
        # 清理临时文件
        await clean_temp_files([video_file, audio_file])
        return True, str(output_filename)

    return False, None


async def get_video_properties(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """获取视频属性"""

    try:
        loop = asyncio.get_event_loop()
        video_info = await loop.run_in_executor(
            None,
            lambda: subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,r_frame_rate",
                    "-of",
                    "default=noprint_wrappers=1",
                    file_path,
                ]
            )
            .decode("utf-8")
            .strip(),
        )

        audio_info = await loop.run_in_executor(
            None,
            lambda: subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=sample_rate,channels,bit_rate",
                    "-of",
                    "default=noprint_wrappers=1",
                    file_path,
                ]
            )
            .decode("utf-8")
            .strip(),
        )

        return video_info, audio_info
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while getting video properties: {e}")
        return None, None


def compare_formats(
    downloaded_video_info: str,
    downloaded_audio_info: str,
    best_video: Optional[Dict[str, Any]],
    best_audio: Dict[str, Any],
) -> Tuple[bool, bool]:
    """对比视频和音频格式"""

    video_match = False
    audio_match = False

    # 解析ffprobe的输出
    video_width = int(re.search(r"width=(\d+)", downloaded_video_info).group(1))
    video_height = int(re.search(r"height=(\d+)", downloaded_video_info).group(1))

    audio_sample_rate = int(
        re.search(r"sample_rate=(\d+)", downloaded_audio_info).group(1)
    )
    audio_channels = int(re.search(r"channels=(\d+)", downloaded_audio_info).group(1))

    # 对比视频格式
    if best_video and (
        best_video.get("width") == video_width
        and best_video.get("height") == video_height
    ):
        video_match = True
        print(f"Matching video format found: {best_video}")

    # 对比音频格式
    if best_audio and (
        best_audio.get("asr") == audio_sample_rate
        and best_audio.get("audio_channels") == audio_channels
    ):
        audio_match = True
        print(f"Matching audio format found: {best_audio}")

    return video_match, audio_match


def extract_video_id(url):
    """从YouTube URL中提取视频ID"""
    youtube_regex = (
        r"(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|user\/\w+\/|playlist\?list=)|"
        r"youtu\.be\/)"
        r"([\w-]{11})"
    )
    match = re.search(youtube_regex, url)
    return match.group(1) if match else None


def is_youtube_url(url):
    """检查URL是否为有效的YouTube网址"""
    # 基本URL格式验证
    youtube_regex = (
        r"^(?:https?:\/\/)?(?:www\.)?"
        r"(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|user\/\w+\/|playlist\?list=)|"
        r"youtu\.be\/)"
        r"([\w-]{11})?"  # 视频ID格式，对于播放列表可能没有视频ID
    )

    return bool(re.match(youtube_regex, url))


def is_playlist(url):
    """检查URL是否为YouTube播放列表"""
    playlist_regex = r"(?:youtube\.com\/(?:playlist\?list=|watch\?.*?&list=)|youtu\.be\/.*?\?list=)([\w-]+)"
    return bool(re.search(playlist_regex, url))


def extract_playlist_id(url):
    """从YouTube URL中提取播放列表ID"""
    playlist_regex = r"(?:youtube\.com\/(?:playlist\?list=|watch\?.*?&list=)|youtu\.be\/.*?\?list=)([\w-]+)"
    match = re.search(playlist_regex, url)
    return match.group(1) if match else None


def get_youtube_url():
    """获取YouTube视频URL"""
    while True:
        url = input("请输入YouTube视频或播放列表URL(输入q退出): ").strip()
        if url.lower() == "q":
            print("程序退出...")
            exit(0)
        if url and is_youtube_url(url):
            if is_playlist(url):
                playlist_id = extract_playlist_id(url)
                # 构建标准化的播放列表URL
                return f"https://www.youtube.com/playlist?list={playlist_id}", True
            else:
                video_id = extract_video_id(url)
                if video_id:
                    # 构建标准化的视频URL
                    return f"https://www.youtube.com/watch?v={video_id}", False
                else:
                    print("无法从URL中提取视频ID。")
                    continue
        print("请输入一个有效的YouTube视频或播放列表URL。")


def get_windows_proxy():
    """获取Windows系统代理设置"""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_READ,
        ) as key:
            proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            if proxy_enable:
                proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
                # 修改：确保返回正确格式的代理地址
                if proxy_server and ":" in proxy_server:
                    if not proxy_server.startswith(("http://", "https://")):
                        return f"http://{proxy_server}"
                    return proxy_server
    except (WindowsError, TypeError):
        pass
    return None


def get_system_proxy():
    """获取系统代理"""
    if platform.system() == "Windows":
        return get_windows_proxy()
    else:
        http_proxy = os.environ.get("http_proxy")
        https_proxy = os.environ.get("https_proxy")
        return http_proxy or https_proxy


def get_proxy_config():
    """获取代理配置"""
    system_proxy = get_system_proxy()
    if system_proxy:
        print(f"检测到系统代理: {system_proxy}")
        while True:
            use_proxy = input("是否使用系统代理? (y/n): ").strip().lower()
            if use_proxy == "y":
                return system_proxy
            elif use_proxy == "n":
                break
            else:
                print("请输入 y 或 n")

    while True:
        use_proxy = input("是否手动设置代理? (y/n): ").strip().lower()
        if use_proxy == "y":
            proxy = input("请输入代理地址: ").strip()
            return proxy
        elif use_proxy == "n":
            break
        else:
            print("请输入 y 或 n")

    return None


async def download_with_resume(
    url: str, file_path: str, proxy: Optional[str] = None
) -> bool:
    """支持断点续传的下载函数"""
    try:
        # 设置请求头和代理
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        proxies = {"http": proxy, "https": proxy} if proxy else None

        # 获取已下载文件的大小
        file_size = 0
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            headers["Range"] = f"bytes={file_size}-"

        # 发送请求
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, headers=headers, proxies=proxies, stream=True),
        )
        total_size = int(response.headers.get("content-length", 0)) + file_size

        mode = "ab" if file_size > 0 else "wb"
        (
            print(f"\n继续从 {file_size/(1024*1024):.1f}MB 处开始下载...")
            if file_size > 0
            else print("\n开始下载...")
        )

        with open(file_path, mode) as f:
            downloaded = file_size
            chunk_size = 8192
            last_print_time = time.time()
            last_downloaded = downloaded

            # 创建迭代器
            chunks_iterator = response.iter_content(chunk_size=chunk_size)

            while True:
                # 异步获取下一个数据块
                try:
                    chunk = await loop.run_in_executor(
                        None, lambda: next(chunks_iterator, None)
                    )
                except StopIteration:
                    break

                if not chunk:
                    break

                f.write(chunk)
                downloaded += len(chunk)

                # 每秒更新一次下载进度
                current_time = time.time()
                if current_time - last_print_time >= 1.0:
                    speed = (downloaded - last_downloaded) / (
                        current_time - last_print_time
                    )
                    speed_text = f"{speed/1024/1024:.2f}MB/s"

                    if total_size > 0:
                        percent = downloaded * 100 / total_size
                        print(
                            f"\r下载进度: {percent:.1f}% | "
                            f"已下载: {downloaded/(1024*1024):.1f}MB / "
                            f"{total_size/(1024*1024):.1f}MB | "
                            f"速度: {speed_text}",
                            end="",
                        )
                    else:
                        print(
                            f"\r已下载: {downloaded/(1024*1024):.1f}MB | "
                            f"速度: {speed_text}",
                            end="",
                        )

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


async def download_and_install_ffmpeg(proxy: Optional[str] = None) -> bool:
    """下载并安装 FFmpeg 到当前目录"""
    if platform.system() != "Windows":
        print("自动安装只支持 Windows 系统")
        return False

    temp_dir = None
    try:
        print("\n正在下载 FFmpeg...")
        temp_dir = Path.cwd() / "temp_ffmpeg"
        temp_dir.mkdir(exist_ok=True)

        zip_path = temp_dir / "ffmpeg.zip"
        extract_path = temp_dir / "ffmpeg"

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
                    if await download_with_resume(url, str(zip_path), proxy):
                        # 验证下载的文件
                        if zip_path.exists() and zipfile.is_zipfile(zip_path):
                            download_success = True
                            break
                        else:
                            print(
                                f"\n下载的文件无效,正在重试({retry + 1}/{max_retries})..."
                            )
                            if zip_path.exists():
                                zip_path.unlink()
                except Exception as e:
                    print(f"\n下载出错: {str(e)}")
                    if retry < max_retries - 1:
                        print(f"等待 5 秒后重试({retry + 1}/{max_retries})...")
                        await asyncio.sleep(5)
                    continue

            if download_success:
                break

        if not download_success:
            print("\n所有下载地址均失败，请稍后重试或手动安装")
            return False

        # 解压后只复制需要的文件到当前目录
        print("正在解压并复制必要文件...")
        loop = asyncio.get_event_loop()
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            await loop.run_in_executor(None, zip_ref.extractall, extract_path)

        ffmpeg_dirs = [d for d in os.listdir(extract_path) if "ffmpeg" in d.lower()]
        if not ffmpeg_dirs:
            print("无法找到 FFmpeg 目录")
            return False

        bin_path = extract_path / ffmpeg_dirs[0] / "bin"

        # 复制必要的可执行文件到当前目录
        for file in ["ffmpeg.exe", "ffprobe.exe"]:
            src = bin_path / file
            dst = Path.cwd() / file
            if src.exists():
                await loop.run_in_executor(None, shutil.copy2, src, dst)

        print("FFmpeg 文件已复制到当前目录！")
        return True

    except Exception as e:
        print(f"安装 FFmpeg 时出错: {str(e)}")
        return False
    finally:
        # 清理临时文件
        if temp_dir and temp_dir.exists():
            try:
                await loop.run_in_executor(None, shutil.rmtree, temp_dir)
            except Exception as e:
                print(f"清理临时文件时出错: {str(e)}")


async def check_ffmpeg(proxy: Optional[str] = None) -> bool:
    """检查当前目录或系统是否安装了 ffmpeg"""
    current_dir = Path.cwd()
    ffmpeg_path = current_dir / "ffmpeg.exe"
    ffprobe_path = current_dir / "ffprobe.exe"

    if ffmpeg_path.exists() and ffprobe_path.exists():
        return True

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
            ),
        )
        return True
    except FileNotFoundError:
        print("\nFFmpeg 未安装！")
        if platform.system() == "Windows":
            print("\n是否要下载 FFmpeg 到当前目录？(y/n): ", end="")
            if input().strip().lower() == "y":
                return await download_and_install_ffmpeg(proxy)
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


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="YouTube视频下载器")
    parser.add_argument("--only-audio", action="store_true", help="只下载音频")
    parser.add_argument(
        "--concurrent", "-c", type=int, default=1, help="并行下载数量(1-10)，默认为1"
    )
    parser.add_argument(
        "--fragments",
        "-f",
        type=int,
        default=3,
        help="单个视频的并行片段下载数量(1-10)，默认为3",
    )
    return parser.parse_args()


async def get_playlist_info(
    url: str, proxy: Optional[str] = None
) -> Tuple[bool, Optional[str], Optional[List[Dict[str, Any]]]]:
    """获取播放列表信息"""
    ydl_opts = {
        "extract_flat": True,  # 不下载视频，只获取基本信息
        "proxy": proxy,
    }

    try:
        loop = asyncio.get_event_loop()
        async with asyncio.Lock():
            info_dict = await loop.run_in_executor(
                None,
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False),
            )

            # 检查是否是播放列表
            if "entries" in info_dict:
                playlist_title = info_dict.get("title", "playlist")
                entries = info_dict["entries"]
                return True, playlist_title, entries
            else:
                return False, None, None
    except Exception as e:
        print(f"获取播放列表信息失败: {str(e)}")
        return False, None, None


async def download_single_video_async(
    video_info: Dict[str, Any],
    output_dir: str,
    proxy: Optional[str] = None,
    only_audio: bool = False,
    concurrent_fragments: int = 3,
) -> bool:
    """异步下载单个视频"""
    video_url = (
        video_info.get("url")
        or f"https://www.youtube.com/watch?v={video_info.get('id')}"
    )
    video_title = video_info.get("title")
    video_index = video_info.get("playlist_index", "")

    if video_index:
        prefix = f"{video_index:02d}-"
    else:
        prefix = ""

    if not video_title:
        video_title = f"video-{video_info.get('id', 'unknown')}"

    # 显示正在下载的视频信息
    print(f"\n开始下载: {prefix}{video_title}")

    try:
        # 获取视频格式
        available_formats, info_dict = await get_available_formats(video_url, proxy)

        # 获取最佳视频和音频格式
        best_video, best_audio = select_best_formats(available_formats)

        if not best_audio:
            print(f"无法获取音频格式: {video_title}")
            return False

        if not only_audio and not best_video:
            print(f"无法获取视频格式: {video_title}")
            return False

        # 下载视频
        download_success, output_file = await download_with_progress(
            video_url,
            best_video,
            best_audio,
            f"{prefix}{video_title}",
            proxy,
            only_audio,
            output_dir,
            concurrent_fragments,
        )

        if download_success:
            print(f"\n视频下载完成: {prefix}{video_title}")
            return True
        else:
            print(f"\n视频下载失败: {prefix}{video_title}")
            return False

    except Exception as e:
        print(f"\n下载视频时出错 ({prefix}{video_title}): {str(e)}")
        return False


async def download_playlist_async(
    url: str,
    proxy: Optional[str] = None,
    only_audio: bool = False,
    concurrent_downloads: int = 3,
    concurrent_fragments: int = 3,
) -> bool:
    """异步下载播放列表"""
    # 获取播放列表信息
    is_playlist, playlist_title, entries = await get_playlist_info(url, proxy)

    if not is_playlist or not entries:
        print("无法获取播放列表信息或URL不是播放列表")
        return False

    # 创建下载目录
    safe_playlist_title = sanitize_filename(playlist_title)
    download_dir = Path.cwd() / "downloads" / safe_playlist_title
    download_dir.mkdir(exist_ok=True, parents=True)

    print(f"\n开始下载播放列表: {playlist_title}")
    print(f"共 {len(entries)} 个视频，设置并行下载数量: {concurrent_downloads}")

    # 限制最大并发数
    effective_concurrent = min(concurrent_downloads, len(entries))

    # 使用线程池执行器运行异步任务
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=effective_concurrent
    ) as executor:
        # 使用队列管理下载任务
        download_queue = asyncio.Queue()

        # 添加所有视频到队列
        for entry in entries:
            await download_queue.put(entry)

        # 创建并发任务
        tasks = []
        for i in range(effective_concurrent):
            task = asyncio.create_task(
                worker(
                    i,
                    download_queue,
                    safe_playlist_title,
                    proxy,
                    only_audio,
                    concurrent_fragments,
                )
            )
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks)

        # 计算成功下载数量
        success_count = sum(r for r in results)

    print(f"\n播放列表下载完成: {playlist_title}")
    print(f"下载[成功/总数]: {success_count}/{len(entries)}")
    print(f"文件保存在: downloads/{safe_playlist_title}/")

    return success_count > 0


async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    output_dir: str,
    proxy: Optional[str] = None,
    only_audio: bool = False,
    concurrent_fragments: int = 3,
) -> int:
    """工作线程，从队列获取视频并下载"""
    success_count = 0

    while not queue.empty():
        try:
            # 获取下一个要下载的视频
            entry = await queue.get()

            print(
                f"工作线程 {worker_id+1}: 开始下载 {entry.get('title', entry.get('id', 'unknown'))}"
            )

            # 下载视频
            if await download_single_video_async(
                entry, output_dir, proxy, only_audio, concurrent_fragments
            ):
                success_count += 1

        except asyncio.CancelledError:
            # 任务被取消
            break
        except Exception as e:
            print(f"工作线程 {worker_id+1} 出错: {str(e)}")
        finally:
            # 标记任务完成
            queue.task_done()

    return success_count


async def main():
    try:
        # 解析命令行参数
        args = parse_arguments()

        print("\nYouTube视频下载器启动...")
        print("=" * 50 + "\n")

        if args.only_audio:
            print("已启用仅下载音频模式")

        # 检查并发下载参数是否有效
        concurrent_downloads = args.concurrent
        if concurrent_downloads < 1 or concurrent_downloads > 10:
            print(f"并行下载数量({concurrent_downloads})超出范围，已重置为1")
            concurrent_downloads = 1
        elif concurrent_downloads > 1:
            print(f"已设置并行下载数量: {concurrent_downloads}")

        # 检查并发片段下载参数是否有效
        concurrent_fragments = args.fragments
        if concurrent_fragments < 1 or concurrent_fragments > 10:
            print(f"并行片段下载数量({concurrent_fragments})超出范围，已重置为3")
            concurrent_fragments = 3
        else:
            print(f"已设置单个视频并行片段下载数量: {concurrent_fragments}")

        # 先获取代理设置
        proxy = get_proxy_config()

        # 检查 ffmpeg 是否安装，传入代理参数
        if not await check_ffmpeg(proxy):
            print("\n请安装 FFmpeg 后重试")
            return

        # 获取视频或播放列表URL
        url, is_playlist_url = get_youtube_url()

        # 处理播放列表
        if is_playlist_url:
            print("\n检测到播放列表URL")

            # 询问用户是否下载整个播放列表
            while True:
                choice = input(f"\n是否下载整个播放列表? (y/n): ").strip().lower()
                if choice == "y":
                    # 如果未通过命令行参数设置并行下载，则询问用户
                    if args.concurrent == 1:
                        # 询问用户想要使用的并发下载数量
                        while True:
                            try:
                                concurrent_input = input(
                                    "\n请输入并行下载数量(1-10，默认为1): "
                                ).strip()
                                if not concurrent_input:  # 用户直接按回车，使用默认值
                                    break
                                user_concurrent = int(concurrent_input)
                                if 1 <= user_concurrent <= 10:
                                    concurrent_downloads = user_concurrent
                                    break
                                else:
                                    print("请输入1-10之间的数字")
                            except ValueError:
                                print("请输入有效的数字")

                    # 使用新的播放列表下载方法，传入并发下载数量
                    await download_playlist_async(
                        url,
                        proxy,
                        args.only_audio,
                        concurrent_downloads,
                        concurrent_fragments,
                    )
                    return
                elif choice == "n":
                    print("取消下载播放列表")
                    return
                else:
                    print("请输入 y 或 n")

        # 处理单个视频
        print("\n获取视频信息中...")
        available_formats, info_dict = await get_available_formats(url, proxy)

        # 获取视频标题
        video_title = info_dict.get("title", "downloaded_video")
        print(f"视频标题: {video_title}")

        best_video, best_audio = select_best_formats(available_formats)
        if not best_audio:
            print("无法获取音频格式")
            return

        if not args.only_audio and not best_video:
            print("无法获取视频格式")
            return

        download_success, output_file = await download_with_progress(
            url,
            best_video,
            best_audio,
            video_title,
            proxy,
            args.only_audio,
            concurrent_fragments=concurrent_fragments,
        )

        if download_success:
            print("\n\n下载完成!")
            print(f"文件保存在: {output_file}")

            if not args.only_audio:
                video_info, audio_info = await get_video_properties(output_file)
                if video_info and audio_info:
                    video_match, audio_match = compare_formats(
                        video_info, audio_info, best_video, best_audio
                    )
                    if video_match and audio_match:
                        print("视频和音频格式验证通过")
                    else:
                        print("警告:下载的视频或音频格式与预期不符")

    except KeyboardInterrupt:
        print("\n\n用户取消下载")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
