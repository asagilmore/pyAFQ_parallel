import os.path as op

from AFQ.api.group import GroupAFQ

import argparse
import AFQ.data.fetch as afd

import psutil
import uuid
import multiprocessing
import threading
import time
import test_utils
import os
import csv
import configparser
import tempfile
import shutil

cpu_count = multiprocessing.cpu_count()
memory_size = psutil.virtual_memory().total
runTimeData = []


def save_data(filename):
    global runTimeData

    # specify the names for CSV column headers
    fieldnames = runTimeData[0].keys() if runTimeData else ValueError(
                                                                    "No data"
                                                                    "to save")

    # writing to csv file
    with open(filename, 'a', newline='') as csvfile:
        # creating a csv writer object
        csvwriter = csv.DictWriter(csvfile, fieldnames=fieldnames)
        # writing headers (field names) if the file doesn't exist or it is empty
        if not os.path.isfile(filename) or os.path.getsize(filename) == 0:
            csvwriter.writeheader()

        # writing the data rows
        csvwriter.writerows(runTimeData)

    runTimeData.clear()


def generate_streamlines(tracking_params, hcp_access, hcp_secret_access,
                         save=True):

    global runTimeData, cpu_count, memory_size

    monitor = test_utils.MemoryMonitor(1)

    print("running generate_streamlines with params: ", tracking_params)

    _, hcp_bids = afd.fetch_hcp([100206])
    myafq = GroupAFQ(
        bids_path=hcp_bids,
        preproc_pipeline="dmriprep",
        viz_backend_spec='plotly_no_gif',
        tracking_params=tracking_params)

    myafq.export_up_to("streamlines")

    monitor_thread = threading.Thread(target=monitor.monitor_memory)
    monitor_thread.start()

    start = time.time()
    myafq.export('streamlines')
    end = time.time()

    # Delete all contents of the folder
    shutil.rmtree(hcp_bids)

    #Stop tracking memeory
    monitor.stop_monitor = True
    monitor_thread.join()

    # grab memory stats
    memory_usage, average_memory_usage = monitor.get_memory_usage()

    runTime = end-start
    print(f"Elapsed time: {end - start} seconds")

    if (save):
        runTimeData.append({'time': runTime,
                            'cpu_count': cpu_count,
                            'memory_size': memory_size,
                            'avg_mem': average_memory_usage,
                            'mem_useage': memory_usage,
                            'params': tracking_params})
    else:
        print("save turned off, runTime not saved")

    return runTime


def add_aws_profile(profile_name, aws_access_key_id, aws_secret_access_key):
    credentials_file = os.path.expanduser('~/.aws/credentials')


    # Check if the file exists
    if not os.path.isfile(credentials_file):
        os.makedirs(os.path.dirname(credentials_file), exist_ok=True)
        open(credentials_file, 'a').close()

    # Create a ConfigParser object
    config = configparser.RawConfigParser()

    # Read the existing AWS credentials file
    config.read(credentials_file)

    # Add the new profile
    if not config.has_section(profile_name):
        config.add_section(profile_name)
    config.set(profile_name, 'aws_access_key_id', aws_access_key_id)
    config.set(profile_name, 'aws_secret_access_key', aws_secret_access_key)

    # Write the changes back to the file
    with open(credentials_file, 'w') as f:
        config.write(f)

    print(f"Profile '{profile_name}' added to {credentials_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_seeds", type=int, default=1)
    parser.add_argument("--random_seeds", type=bool, default=False)
    parser.add_argument("--min_chunks", type=int, default=None)
    parser.add_argument("--max_chunks", type=int, default=None)
    parser.add_argument("--rng_seeds", default=None)
    parser.add_argument("--num_runs", type=int, default=1)
    parser.add_argument("--num_cpus", type=int, default=None)
    parser.add_argument('--filename', type=str, default='data.csv')
    parser.add_argument('--s3bucket', type=str, default=None)
    parser.add_argument('--s3_access_key_id', type=str, default=None)
    parser.add_argument('--s3_secret_access_key', type=str, default=None)
    parser.add_argument('--exp_chunks', type=bool, default=False)
    parser.add_argument('--hcp_access_key_id', type=str, required=True)
    parser.add_argument('--hcp_secret_access_key', type=str, required=True)

    args = parser.parse_args()

    base_filename, __ = os.path.splitext(args.filename)

    uuid = uuid.uuid4().hex
    unique_object_name = f"{base_filename}_{uuid}.csv"

    add_aws_profile('hcp', args.hcp_access_key_id,
                    args.hcp_secret_access_key)

    if args.num_cpus:
        cpu_count = args.num_cpus

    # Use the command line arguments as needed in your code
    tracking_params = dict(n_seeds=args.num_seeds,
                           random_seeds=args.random_seeds,
                           trx=True,
                           num_chunks=None)

    if args.rng_seeds:
        tracking_params['rng_seeds'] = args.rng_seeds

    for i in range(args.num_runs):
        if args.min_chunks and args.max_chunks:

            for num_chunks in range(args.min_chunks, args.max_chunks+1):
                if args.exp_chunks:
                    tracking_params['num_chunks'] = 2**num_chunks
                else:
                    tracking_params['num_chunks'] = num_chunks
                generate_streamlines(tracking_params, args.hcp_access_key_id,
                                     args.hcp_secret_access_key)
                save_data(args.filename)
                test_utils.upload_to_s3(
                        args.filename, args.s3bucket,
                        object_name=unique_object_name,
                        aws_access_key_id=args.s3_access_key_id,
                        aws_secret_access_key=args.s3_secret_access_key)
        else:
            tracking_params['num_chunks'] = 1
            generate_streamlines(tracking_params, args.hcp_access_key_id,
                                 args.hcp_secret_access_key)
            save_data(args.filename)
            test_utils.upload_to_s3(
                    args.filename, args.s3bucket,
                    object_name=unique_object_name,
                    aws_access_key_id=args.s3_access_key_id,
                    aws_secret_access_key=args.s3_secret_access_key)