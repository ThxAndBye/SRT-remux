import json
import os
import shutil

root_directory = "[enter root path here]"


def handle_directory(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        handle_files(files, root)
        for dir in dirs:
            handle_directory(dir)


def handle_files(files, root):
    for file in files:
        check_for_srt(file, root)


def check_for_srt(file, root):
    command = 'mkvmerge.exe "' + root + "\\" + file + '" -i -F json'
    result = os.popen(command)
    json_result = json.loads(result.read())

    # check if the file is understood by mkvtoolnix and if it conrains srt tracks
    if json_result['container']['recognized']:
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
        id = str(srt_track['id'])
        uid = str(srt_track['properties']['uid'])
        track_extract = id + ':"' + root + '\\temp\\' + uid + '.srt"'
        track_extract_commands.append(track_extract)

    # construct and execute the command for extracting
    command = 'mkvextract.exe "' + root + "\\" + file + '" tracks ' + ' '.join(track_extract_commands)
    os.system(command)
    print("Extracting done")


def remux_srt(file, root, srt_tracks, non_srt_tracks):
    # it's important to know if there are other subtile formats present as those are kept
    non_srt_track_nrs = []
    for srt_track in non_srt_tracks:
        non_srt_track_nrs.append(str(srt_track['id']))

    # requiered information to mux the srt files with the original information like language or name
    track_mux_commands = []
    for srt_track in srt_tracks:
        uid = str(srt_track['properties']['uid'])
        language = srt_track['properties']['language']
        track_name = srt_track['properties']['track_name']
        default_track = srt_track['properties']['default_track']
        forced_track = srt_track['properties']['forced_track']
        add_subtitle = '--language 0:' + language + ' --track-name 0:"' + track_name + '"' + \
                       (' --default-track 0:yes' if default_track else '') + (' --forced-track 0:yes ' if forced_track else ' ') + \
                       '"' + root + "\\temp\\" + uid + '.srt"'
        track_mux_commands.append(add_subtitle)

    # construct and execute the command for muxing
    command = 'mkvmerge.exe --ui-language en ' + \
              '--output "' + root + "\\temp\\" + file + '" ' + \
              ('-S' if len(non_srt_track_nrs) == 0 else '-s ' + ','.join(non_srt_track_nrs)) + ' ' + \
              '"' + root + "\\" + file + '" ' + \
              ' '.join(track_mux_commands) + ' ' + \
              '--title "' + os.path.splitext(file)[0] + '" '
    os.system(command)
    print("Remux completed")

def cleanup(file, root):
    # check if new file was created before deleting the original one
    if os.path.isfile(root + "\\temp\\" + file):
        os.remove(root + "\\" + file)
        shutil.move(root + "\\temp\\" + file, root)
        shutil.rmtree(root + "\\temp")


if __name__ == '__main__':
    handle_directory(root_directory)
