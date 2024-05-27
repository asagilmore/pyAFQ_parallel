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


# run csdm with the given engine and vox_per_chunk
# appends the given time, engine, and vox_per_chunk to the data dataframe
# returns the time it took to run
def run_fit(model, engine, data, brain_mask_data, num_chunks, save=True):

    global runTimeData, cpu_count, memory_size

    monitor = test_utils.MemoryMonitor(1)

    ## calc approx vox_per_chunk from num_chunks
    non_zero_count = np.count_nonzero(brain_mask_data)
    chunk_size = non_zero_count // num_chunks
    vox_per_chunk = int(chunk_size)

    print("running with, engine: ", engine, " vox_per_chunk: ", vox_per_chunk,
          " num_chunks: ", num_chunks)

    # start tracking memory useage
    monitor_thread = threading.Thread(target=monitor.monitor_memory)
    monitor_thread.start()

    print(f'engine {engine}')
    start = time.time()
    fit = model.fit(data, mask=brain_mask_data)
    end = time.time()

    #Stop tracking memeory
    monitor.stop_monitor = True
    monitor_thread.join()

    # grab memory stats
    memory_usage, average_memory_usage = monitor.get_memory_usage()

    runTime = end-start

    model_name = model.__class__.__name__

    if (save):
        runTimeData.append({'engine': engine, 'vox_per_chunk': vox_per_chunk,
                            'num_chunks': num_chunks, 'time': runTime,
                            'cpu_count': cpu_count,
                            'memory_size': memory_size,
                            'num_vox': non_zero_count,
                            'avg_mem': average_memory_usage,
                            'mem_useage': memory_usage, 'model': model_name,
                            'data_shape': data.shape})
    else:
        print("save turned off, runTime not saved")

    print("time: ", runTime)

    return runTime


def generate_streamlines(tracking_params, save=True):

    global runTimeData, cpu_count, memory_size

    monitor = test_utils.MemoryMonitor(1)

    print("running generate_streamlines with params: ", tracking_params)

    afd.organize_stanford_data(clear_previous_afq="track")
    myafq = GroupAFQ(
        bids_path=op.join(afd.afq_home, 'stanford_hardi'),
        preproc_pipeline='vistasoft',
        tracking_params=tracking_params,
        viz_backend_spec='plotly_no_gif')

    myafq.export_up_to("streamlines")

    monitor_thread = threading.Thread(target=monitor.monitor_memory)
    monitor_thread.start()

    start = time.time()
    myafq.export('streamlines')
    end = time.time()

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

    args = parser.parse_args()

    base_filename, __ = os.path.splitext(args.filename)

    uuid = uuid.uuid4().hex
    unique_object_name = f"{base_filename}_{uuid}.csv"

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
                generate_streamlines(tracking_params)
                save_data(args.filename)
                test_utils.upload_to_s3(
                        args.filename, args.s3bucket,
                        object_name=unique_object_name,
                        aws_access_key_id=args.s3_access_key_id,
                        aws_secret_access_key=args.s3_secret_access_key)
        else:
            tracking_params['num_chunks'] = 1
            generate_streamlines(tracking_params)
            save_data(args.filename)
            test_utils.upload_to_s3(
                    args.filename, args.s3bucket,
                    object_name=unique_object_name,
                    aws_access_key_id=args.s3_access_key_id,
                    aws_secret_access_key=args.s3_secret_access_key)