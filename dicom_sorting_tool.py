#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import argparse
import pydicom
import shutil
from pathvalidate import sanitize_filepath
from tqdm import tqdm
import re

def get_dicom_attribute(dataset, attribute):
    try:
        return str(getattr(dataset, attribute))
    except AttributeError:
        return 'UNKNOWN'

def read_id_correlation(file_path):
    id_map = {}
    if file_path:
        with open(file_path, 'r') as file:
            for line in file:
                # Use regular expression to split by comma, space, or tab
                parts = re.split(r',|\s|\t', line.strip())
                if len(parts) >= 2:  # Ensure there are at least two parts
                    old_id, new_id = parts[0], parts[1]
                    id_map[old_id] = new_id
                else:
                    print(f"Invalid line format: {line}")
    return id_map

def anonymize_dicom_tags(dataset, id_map=None):
    if 'PatientBirthDate' in dataset:
        dataset.PatientBirthDate = ''
    if 'PatientName' in dataset:
        dataset.PatientName = 'ANONYMIZED'
    if 'PatientID' in dataset and id_map:
        old_id = dataset.PatientID
        if old_id in id_map:
            dataset.PatientID = id_map[old_id]
        else:
            missing_ids.add(old_id)
    return dataset

def copy_dicom_image(src_file, dest_base_dir, pattern, anonymize=False, id_map=None):
    non_dicom_extensions = ['.png', '.jpeg', '.jpg', '.gif', '.bmp']
    if any(src_file.lower().endswith(ext) for ext in non_dicom_extensions):
        return

    try:
        dataset = pydicom.dcmread(src_file)
    except:
        print(f'Not a DICOM file: {src_file}')
        return

    if anonymize or id_map:
        dataset = anonymize_dicom_tags(dataset, id_map)

    for attribute in ['PatientID', 'StudyDate', 'SeriesNumber', 'SeriesDescription']:
        value = get_dicom_attribute(dataset, attribute)
        pattern = pattern.replace(f'%{attribute}%', value)

    dest_directory = sanitize_filepath(os.path.join(dest_base_dir, pattern), platform='auto')
    os.makedirs(dest_directory, exist_ok=True)
    dataset.save_as(os.path.join(dest_directory, os.path.basename(src_file)))

def copy_directory(src_dir, dest_dir, pattern, anonymize, id_map):
    all_files = [os.path.join(root, file) for root, _, files in os.walk(src_dir) for file in files]
    for file in tqdm(all_files, desc="Processing", unit="file"):
        copy_dicom_image(file, dest_dir, pattern, anonymize, id_map)

def sort_dicom(input_dir, output_dir, anonymize, id_map):
    pattern = '%PatientID%/%StudyDate%/%SeriesNumber%_%SeriesDescription%'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    copy_directory(input_dir, output_dir, pattern, anonymize, id_map)

missing_ids = set()

def main():
    parser = argparse.ArgumentParser(description="This script copies and optionally anonymizes DICOM files into a structured directory. It can also replace PatientID based on a correlation file.",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--dicomin', type=str, required=True, help='Path to the input directory containing unsorted DICOM files.')
    parser.add_argument('--dicomout', type=str, required=True, help='Path to the output directory where structured and optionally anonymized DICOM files will be stored.')
    parser.add_argument('--anonymize', action='store_true', help='If specified, anonymizes DICOM tags such as PatientName and PatientBirthDate.')
    parser.add_argument('--ID_correlation', type=str, help='Optional path to a correlation file mapping old PatientIDs to new PatientIDs. \nExpected format: oldID,newID per line.')
    args = parser.parse_args()

    id_map = read_id_correlation(args.ID_correlation) if args.ID_correlation else None

    sort_dicom(args.dicomin, args.dicomout, args.anonymize, id_map)

    if missing_ids:
        log_file_path = 'missing_patient_ids.log'
        with open(log_file_path, 'w') as log_file:
            for missing_id in missing_ids:
                log_file.write(f'{missing_id}\n')
        print(f"Missing PatientIDs logged in '{log_file_path}'.")

if __name__ == '__main__':
    main()
