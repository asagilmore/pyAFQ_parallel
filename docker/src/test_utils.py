import boto3
import psutil
import time


class MemoryMonitor:
    def __init__(self, interval):
        self.interval = interval
        self.memory_usage = []
        self.stop_monitor = False

    def monitor_memory(self):
        while not self.stop_monitor:
            mem_info = psutil.virtual_memory()
            used_memory_GB = mem_info.used / (1024 ** 3)
            self.memory_usage.append(used_memory_GB)
            time.sleep(self.interval)

    def get_memory_usage(self):
        return self.memory_usage, sum(self.memory_usage) / len(self.memory_usage)


def upload_to_s3(file_name, bucket, object_name=None, region_name='us-west-2',
                 aws_access_key_id=None, aws_secret_access_key=None):
    # If S3 object_name was not specified, use file_name
    if object_name is None:
        object_name = file_name

    # Upload the file
    s3_client = boto3.client('s3', region_name=region_name,
                             aws_access_key_id=aws_access_key_id,
                             aws_secret_access_key=aws_secret_access_key)
    response = s3_client.upload_file(file_name, bucket, object_name)
    return True