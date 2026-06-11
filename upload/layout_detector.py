import os


def detect_txt_layout(file_path):
    with open(file_path, 'r', encoding='latin-1') as f:
        first_line = f.readline()

    if first_line[0:8] == '00000020':
        return 'RB'
    return 'AHREAS'
