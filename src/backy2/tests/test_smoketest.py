# This is an port and update of the original smoketest.py
import json
from unittest import TestCase

import os
import random

from backy2.scripts.backy import hints_from_rbd_diff
from backy2.tests.testcase import BackyTestCase

kB = 1024
MB = kB * 1024
GB = MB * 1024

class SmokeTestCase():

    @classmethod
    def patch(self, filename, offset, data=None):
        """ write data into a file at offset """
        if not os.path.exists(filename):
            open(filename, 'wb').close()
        with open(filename, 'r+b') as f:
            f.seek(offset)
            f.write(data)

    @classmethod
    def same(self, file1, file2):
        """ returns False if files differ, True if they are the same """
        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            d1 = f1.read()
            d2 = f2.read()
        return d1 == d2

    def test(self):
        testpath = self.testpath.path
        from_version = None
        version_uids = []
        old_size = 0
        initdb = True
        image_filename = os.path.join(testpath, 'image')
        for i in range(100):
            print('Run {}'.format(i+1))
            hints = []
            if old_size and random.randint(0, 10) == 0:  # every 10th time or so do not apply any changes.
                size = old_size
            else:
                size = 32*4*kB + random.randint(-4*kB, 4*kB)
                old_size = size
                for j in range(random.randint(0, 10)):  # up to 10 changes
                    if random.randint(0, 1):
                        patch_size = random.randint(0, 4*4*kB)
                        data = self.random_bytes(patch_size)
                        exists = "true"
                    else:
                        patch_size = random.randint(0, 4*4*kB)  # we want full blocks sometimes
                        data = b'\0' * patch_size
                        exists = "false"
                    offset = random.randint(0, size - patch_size - 1)
                    print('    Applied change at {}({}):{}, exists {}'.format(offset, int(offset / 4096), patch_size, exists))
                    self.patch(image_filename, offset, data)
                    hints.append({'offset': offset, 'length': patch_size, 'exists': exists})
            # truncate?
            if not os.path.exists(image_filename):
                open(image_filename, 'wb').close()
            with open(image_filename, 'r+b') as f:
                f.truncate(size)

            #copyfile(image_filename, '{}.{}'.format(image_filename, i + 1))

            print('  Applied {} changes, size is {}.'.format(len(hints), size))
            with open(os.path.join(testpath, 'hints'), 'w') as f:
                    f.write(json.dumps(hints))

            backy = self.backyOpen(initdb=initdb)
            initdb = False
            with open(os.path.join(testpath, 'hints')) as hints:
                version_uid = backy.backup(
                    'data-backup',
                    'snapshot-name',
                    'file://' + image_filename,
                    hints_from_rbd_diff(hints.read()),
                    from_version
                )
            backy.close()
            version_uids.append(version_uid)

            backy = self.backyOpen(initdb=initdb)
            self.assertTrue(backy.scrub(version_uid))
            backy.close()
            print('  Scrub successful')
            backy = self.backyOpen(initdb=initdb)
            self.assertTrue(backy.scrub(version_uid, 'file://' + image_filename))
            backy.close()
            print('  Deep scrub successful')
            backy = self.backyOpen(initdb=initdb)
            restore_filename = os.path.join(testpath, 'restore.{}'.format(i + 1))
            backy.restore(version_uid, 'file://' + restore_filename, sparse=False, force=False)
            backy.close()
            self.assertTrue(self.same(image_filename, restore_filename))
            os.unlink(restore_filename)
            print('  Restore successful')

            from_version = version_uid

            # delete old versions
            if len(version_uids) > 10:
                backy = self.backyOpen(initdb=initdb)
                backy.rm(version_uids.pop(0))
                backy.close()

            if (i%7) == 0:
                backy = self.backyOpen(initdb=initdb)
                backy.cleanup_fast(dt=0)
                backy.close()

class SmokeTestCaseSQLLite_File(SmokeTestCase, BackyTestCase, TestCase):

    CONFIG = """
            configurationVersion: '0.1'
            processName: backy2
            logFile: /dev/stderr
            lockDirectory: {testpath}/lock
            hashFunction: blake2b,digest_size=32
            blockSize: 4096
            io:
              file:
                simultaneousReads: 5
            dataBackend:
              type: file
              file:
                path: {testpath}/data
              simultaneousWrites: 5
              simultaneousReads: 5
              bandwidthRead: 0
              bandwidthWrite: 0
            metaBackend: 
              type: sql
              sql:
                engine: sqlite:///{testpath}/backy.sqlite
            """
class SmokeTestCasePostgreSQL_File(SmokeTestCase, BackyTestCase, TestCase):

    CONFIG = """
            configurationVersion: '0.1'
            processName: backy2
            logFile: /dev/stderr
            lockDirectory: {testpath}/lock
            hashFunction: blake2b,digest_size=32
            blockSize: 4096
            io:
              file:
                simultaneousReads: 5
            dataBackend:
              type: file
              file:
                path: {testpath}/data
              simultaneousWrites: 5
              simultaneousReads: 5
              bandwidthRead: 0
              bandwidthWrite: 0
            metaBackend: 
              type: sql
              sql:
                engine: postgresql://backy2:verysecret@localhost:15432/backy2
            """
class SmokeTestCasePostgreSQL_S3(SmokeTestCase, BackyTestCase, TestCase):

    CONFIG = """
            configurationVersion: '0.1'
            processName: backy2
            logFile: /dev/stderr
            lockDirectory: {testpath}/lock
            hashFunction: blake2b,digest_size=32
            blockSize: 4096
            io:
              file:
                simultaneousReads: 5
            dataBackend:
              type: s3
              s3:
                awsAccessKeyId: minio
                awsSecretAccessKey: minio123
                host: 127.0.0.1
                port: 9901
                isSecure: False
                bucketName: backy2
              simultaneousWrites: 5
              simultaneousReads: 5
              bandwidthRead: 0
              bandwidthWrite: 0
            metaBackend: 
              type: sql
              sql:
                engine: postgresql://backy2:verysecret@localhost:15432/backy2
            """

class SmokeTestCasePostgreSQL_S3_Boto3(SmokeTestCase, BackyTestCase, TestCase):

    CONFIG = """
            configurationVersion: '0.1'
            processName: backy2
            logFile: /dev/stderr
            lockDirectory: {testpath}/lock
            hashFunction: blake2b,digest_size=32
            blockSize: 4096
            io:
              file:
                simultaneousReads: 5
            dataBackend:
              type: s3_boto3
              s3_boto3:
                awsAccessKeyId: minio
                awsSecretAccessKey: minio123
                endpointUrl: http://127.0.0.1:9901/
                bucketName: backy2
                multiDelete: true
                addressingStyle: path
              simultaneousWrites: 5
              simultaneousReads: 5
              bandwidthRead: 0
              bandwidthWrite: 0
            metaBackend: 
              type: sql
              sql:
                engine: postgresql://backy2:verysecret@localhost:15432/backy2
            """

class SmokeTestCasePostgreSQL_B2(SmokeTestCase, BackyTestCase, TestCase):

    CONFIG = """
            configurationVersion: '0.1'
            processName: backy2
            logFile: /dev/stderr
            lockDirectory: {testpath}/lock
            hashFunction: blake2b,digest_size=32
            blockSize: 4096
            io:
              file:
                simultaneousReads: 5
            dataBackend:
              type: b2
              b2:
                 accountId: **************
                 applicationKey: **************
                 bucketName: backy2
              simultaneousWrites: 5
              simultaneousReads: 5
              bandwidthRead: 0
              bandwidthWrite: 0
            metaBackend: 
              type: sql
              sql:
                engine: postgresql://backy2:verysecret@localhost:15432/backy2
            """