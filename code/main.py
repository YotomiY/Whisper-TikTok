import platform
import os
import random
import re
import sys
import asyncio
import multiprocessing
from datetime import timedelta
from typing import Tuple

from tqdm import tqdm

# ENV
from dotenv import load_dotenv, find_dotenv

# OpenAI Whisper Model PyTorch
import whisper

# MicrosoftEdge TTS
import edge_tts
from edge_tts import VoicesManager

# FFMPEG (Python)
import ffmpeg

#######################
#        STATIC       #
#######################
jsonData = {"series": "Crazy facts that you did not know",
            "part": 4,
            "outro": "Follow us for more",
            "random": False,
            "path": "F:\\Vari Progetti\\AI_YouTube\\source",
            "texts": ["Did you know that there are more possible iterations of a game of chess than there are atoms in the observable universe? The number of possible legal moves in a game of chess is around 10^120, while the estimated number of atoms in the observable universe is 10^80. This means that if every atom in the universe were a chess game being played out simultaneously, there still wouldn't be enough atoms to represent every possible iteration of the game!", "Example2", "Example 3"]}

#######################
#         CODE        #
#######################


async def main() -> bool:
    load_dotenv(find_dotenv())

    series = jsonData['series']
    part = jsonData['part']
    outro = jsonData['outro']
    path = jsonData['path']

    current_cwd = os.getcwd()
    model = whisper.load_model("base")

    # Text 2 Speech (TikTok API) Batched
    for text in jsonData['texts']:
        req_text, filename = create_full_text(path, series, part, text, outro)
        await tts(req_text, outfile=filename)

        # Whisper Model to create SRT file from Speech recording
        srt_filename = srt_create(model, path, series, part, text, filename)

        os.chdir(current_cwd)
        background_mp4 = random_background()
        file_info = get_info(background_mp4)
        prepare_background(background_mp4, filename_mp3=filename, filename_srt=srt_filename, W=file_info.get('width'), H=file_info.get('height'), duration=int(file_info.get('duration')))

        # Increment part so it can fetch the next text in JSON
        part += 1

    return True

def random_background(folder_path: str = "background"):
    os.chdir(folder_path)
    files = os.listdir(f"{os.getcwd()}")
    random_file = random.choice(files)
    return os.path.abspath(random_file)

def get_info(file_path: str):
    try:
        probe = ffmpeg.probe(file_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        if video_stream is None:
            print('No video stream found', file=sys.stderr)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            bit_rate = int(audio_stream['bit_rate'])
            duration = float(audio_stream['duration'])
            return {'bit_rate': bit_rate, 'duration': duration}
        
        width = int(video_stream['width'])
        height = int(video_stream['height'])
        duration = float(video_stream['duration'])
        print(f"File: {file_path}\nResolution: {width} x {height}\nDuration: {duration} seconds")
        return {'width': width,'height': height, 'duration': duration}
    except ffmpeg.Error as e:
        print(e.stderr, file=sys.stderr)
        sys.exit(1)

def prepare_background(background_mp4, filename_mp3, filename_srt, W: int, H: int, duration:int): 
    # Crop if too large
    if (W > 1080) and (H > 1920):
        W, H = 1080, 1920
    # Get length of MP3 file to be merged with
    audio_info = get_info(filename_mp3)

    output = (
        ffmpeg.input(f"{background_mp4}")
        .filter("crop", f"ih*({W}/{H})", "ih")
        .concat(f"{background_mp4}", )
        .output(
            output_path:=f"{os.getcwd()}{os.sep}background.mp4",
            **{
                "c:v": "h264",
                "b:v": "10M",
                "b:a": "192k",
                "to": audio_info.get('duration'),
                "threads": multiprocessing.cpu_count(),
            },
        )
        .overwrite_output()
    )
    try:
        output.run_async(quiet=False)
    except Exception as e:
        print(e)
        exit()
    return output_path



def srt_create(model, path: str, series: str, part: int, text: str, filename: str) -> bool:
    """
    Srt_create is a function that takes in five arguments: a model for speech-to-text conversion, a path to a directory, a series name, a part number, text content, and a filename for the audio file. The function uses the specified model to convert the audio file to text, and creates a .srt file with the transcribed text and timestamps.

    Args:
        model: A model object used for speech-to-text conversion.
        path (str): A string representing the path to the directory where the .srt file will be created.
        series (str): A string representing the name of the series.
        part (int): An integer representing the part number of the series.
        text (str): A string representing the main content of the audio file.
        filename (str): A string representing the name of the audio file.

    Returns:
        bool: A boolean indicating whether the creation of the .srt file was successful or not.

    """
    transcribe = model.transcribe(filename)
    segments = transcribe['segments']
    for segment in segments:
        startTime = str(0)+str(timedelta(seconds=int(segment['start'])))+',000'
        endTime = str(0)+str(timedelta(seconds=int(segment['end'])))+',000'
        text = segment['text'].upper()
        segmentId = segment['id']+1
        segment = f"{segmentId}\n{startTime} --> {endTime}\n{text[1:] if text[0] == ' ' else text}\n\n"

        srtFilename = os.path.join(
            f"{path}\\{series}\\", f"{series.replace(' ', '')}_{part}.srt")
        with open(srtFilename, 'a', encoding='utf-8') as srtFile:
            srtFile.write(segment)
    
    return srtFilename


def batch_create(filename: str) -> None:
    """
    Batch_create is a function that takes in a filename as input and creates a new file with the concatenated contents of all the files in the './batch/' directory, sorted in alphanumeric order.

    Args:
    filename (str): A string representing the name of the output file to be created.

    Returns:
    None: This function does not return anything, but creates a new file with the contents of all the files in the './batch/' directory sorted in alphanumeric order.

    """
    with open(filename, 'wb') as out:
        def sorted_alphanumeric(data):
            def convert(text): return int(
                text) if text.isdigit() else text.lower()
            def alphanum_key(key): return [convert(c)
                                           for c in re.split('([0-9]+)', key)]
            return sorted(data, key=alphanum_key)

        for item in sorted_alphanumeric(os.listdir('./batch/')):
            filestuff = open('./batch/' + item, 'rb').read()
            out.write(filestuff)


def create_directory(path: str, directory: str) -> bool:
    """
    Create_directory is a function that takes in two arguments: a path to a directory and a name for a new directory. The function creates a new directory with the specified name in the specified path if it doesn't already exist, and returns a boolean indicating whether the directory was created.

    Args:
    path (str): A string representing the path to the directory where the new directory will be created.
    directory (str): A string representing the name of the new directory.

    Returns:
    bool: Returns True if a new directory was created, False otherwise.

    """
    current_dir = os.getcwd()
    os.chdir(path)
    if not os.path.isdir(directory):
        os.mkdir(directory)
        os.chdir(current_dir)
        return True
    return False


def create_full_text(path: str = '', series: str = '', part: int = 1, text: str = '', outro: str = '') -> Tuple[str, str]:
    """
    Create_full_text is a function that takes in four arguments: a path to a directory, a series name, a part number, text content, and outro content. The function creates a new text with series, part number, text, and outro content and returns a tuple containing the resulting text and the filename.

    Args:
        path (str): A string representing the path to the directory where the new text file will be created. Default value is an empty string.
        series (str): A string representing the name of the series. Default value is an empty string.
        part (int): An integer representing the part number of the series. Default value is 1.
        text (str): A string representing the main content of the text file. Default value is an empty string.
        outro (str): A string representing the concluding remarks of the text file. Default value is an empty string.

    Returns:
        Tuple[str, str]: A tuple containing the resulting text and the filename of the text file.

    """
    req_text = f"{series} Part {part}.\n{text}\n{outro}"
    filename = f"{path}\\{series}\\{series.replace(' ', '')}_{part}.mp3"
    create_directory(path, directory=series)
    return req_text, filename


async def tts(final_text: str, voice: str = "en-US-ChristopherNeural", random_voice: bool = False, stdout: bool = False, outfile: str = "tts.mp3") -> bool:
    """
    Tts is an asynchronous function that takes in four arguments: a final text string, a voice string, a boolean value for random voice selection, a boolean value to indicate if output should be directed to standard output or not, and a filename string for the output file. The function uses Microsoft Azure Cognitive Services to synthesize speech from the input text using the specified voice, and saves the output to a file or prints it to the console.

    Args:
        final_text (str): A string representing the text to be synthesized into speech.
        voice (str): A string representing the name of the voice to be used for speech synthesis. Default value is "en-US-ChristopherNeural".
        random_voice (bool): A boolean value indicating whether to randomly select a male voice for speech synthesis. Default value is False.
        stdout (bool): A boolean value indicating whether to output the speech to the console or not. Default value is False.
        outfile (str): A string representing the name of the output file. Default value is "tts.mp3".

    Returns:
        bool: A boolean indicating whether the speech synthesis was successful or not.

    """
    voices = await VoicesManager.create()
    if random_voice:
        voices = voices.find(Gender="Male", Locale="en-US")
        voice = random.choice(voices)["Name"]
    communicate = edge_tts.Communicate(final_text, voice)
    if not stdout:
        await communicate.save(outfile)
    return True

if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
