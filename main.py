import io
import json
import os
import shutil
import re
import sys

# to prevent fixing files twice
current_mkvmerge_version = ""


def handle_directory(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        for file in files:
            check_for_srt(file, root)


def check_for_srt(file, root):
    command = 'mkvmerge.exe "' + os.path.join(root, file) + '" -i -F json'
    result = os.popen(command)
    result = io.BytesIO(result.buffer.read())
    json_result = json.loads(result.read())

    # check if the file is understood by mkvtoolnix and if it contains srt tracks
    if json_result['container']['recognized']:
        if json_result['container']['type'] == "Matroska" and json_result['container']['properties']['writing_application'] != current_mkvmerge_version:
            srt_tracks = []
            non_srt_tracks = []
            for track in json_result['tracks']:
                if track['type'] == "subtitles":
                    if track['codec'] == "SubRip/SRT":
                        srt_tracks.append(track)
                    else:
                        non_srt_tracks.append(track)
            if len(srt_tracks) > 0:
                extract_srt(file, root, srt_tracks)
                remux_srt(file, root, srt_tracks, non_srt_tracks)
                cleanup(file, root)


def extract_srt(file, root, srt_tracks):
    track_extract_commands = []
    # gather some information about the subtitle tacks to extract them to ./temp
    for srt_track in srt_tracks:
        track_id = str(srt_track['id'])
        uid = str(srt_track['properties']['uid'])
        track_extract = track_id + ':"' + os.path.join(root, "temp", uid + ".srt") + '"'
        track_extract_commands.append(track_extract)

    # construct and execute the command for extracting
    input_file = '"' + os.path.join(root, file) + '"'
    command = 'mkvextract.exe ' + input_file + ' tracks ' + ' '.join(track_extract_commands)

    print("Starting to extract subtitles from: " + input_file)
    os.system(command)
    print("Extracting done")


# construct and execute the command for muxing
def remux_srt(file, root, srt_tracks, non_srt_tracks):
    # it's important to know if there are other subtile formats present as those are kept
    non_srt_track_nrs = []
    for srt_track in non_srt_tracks:
        non_srt_track_nrs.append(str(srt_track['id']))

    # required information to mux the srt files with the original information like language or name
    track_mux_commands = []
    for srt_track in srt_tracks:
        language = '--language 0:' + srt_track['properties']['language']
        track_name = '--track-name 0:"' + (
            srt_track['properties']['track_name'] if 'track_name' in srt_track['properties'] else gen_track_name(
                srt_track['properties'])) + '"'
        default_track = ('--default-track 0:yes' if srt_track['properties']['default_track'] else '')
        forced_track = ('--forced-track 0:yes' if srt_track['properties']['forced_track'] else '')
        uid = str(srt_track['properties']['uid'])
        srt_file = '"' + os.path.join(root, "temp", uid + ".srt") + '"'

        add_subtitle = language + ' ' + track_name + ' ' + default_track + ' ' + forced_track + ' ' + srt_file
        add_subtitle = re.sub(' +', ' ', add_subtitle)
        track_mux_commands.append(add_subtitle)

    output_file = '--output ' + '"' + os.path.join(root, "temp", file) + '"'
    subtitle_remove = ('-S' if len(non_srt_track_nrs) == 0 else '-s ' + ','.join(non_srt_track_nrs))
    input_file = '"' + os.path.join(root, file) + '"'

    command = 'mkvmerge.exe --ui-language en ' + \
              output_file + ' ' + subtitle_remove + ' ' + input_file + ' ' + \
              ' '.join(track_mux_commands) + ' ' + \
              '--title "' + os.path.splitext(file)[0] + '" ' + \
              '--abort-on-warnings'

    if os.system(command) != 0:
        print("Some problem occurred with " + file + ", aborting ...")
        shutil.rmtree(os.path.join(root, "temp"))
        exit(0)


def gen_track_name(properties):
    language = properties['language']
    forced = 'FORCED' if properties['forced_track'] else 'SUBS'
    track_name = language.upper() + ' - ' + forced
    return track_name


def cleanup(file, root):
    # check if new file was created before deleting the original one
    output_file = os.path.join(root, "temp", file)

    if os.path.isfile(output_file) and check_mkv(output_file):
        os.remove(os.path.join(root, file))
        shutil.move(output_file, root)
        print("Remux completed. Cleaning up ...")
    else:
        print("Error muxing new file. Cleaning up ...")
    shutil.rmtree(os.path.join(root, "temp"))


def check_mkv(file):
    command = 'MediaInfo.exe --Output=JSON "' + file + '"'
    result = os.popen(command)
    result = io.BytesIO(result.buffer.read())
    json_result = json.loads(result.read())

    is_ok = True
    if 'extra' in json_result['media']['track'][0]:
        is_truncated = True if ('IsTruncated' in json_result['media']['track'][0]['extra']) else False
        segment_size_is_zero = True if ('SegmentSizeIsZero' in json_result['media']['track'][0]['extra']) else False
        is_ok = not is_truncated and not segment_size_is_zero
    return is_ok


if __name__ == '__main__':
    current_mkvmerge_version = os.popen("mkvmerge.exe --version").read().split("\n")[0]
    current_mediainfocli_version = os.popen("MediaInfo.exe --version").read().split("\n")[1]
    print("SRT-remux by Thx And Bye\n"
          "Working with: " + current_mkvmerge_version + " and " + current_mediainfocli_version)
    try:
        root_directory = sys.argv[1]
    except IndexError:
        root_directory = ""
    if os.path.isdir(root_directory):
        print("Starting to remux Matroska files with SRT tracks, starting at: " + root_directory)
        handle_directory(root_directory)
    else:
        print("Error: Not a valid directory provided.\n\n" + \
              sys.argv[0] + " <directory>")
