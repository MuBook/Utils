#!/usr/bin/env python
import argparse
import requests
import os
import time
import threading


class Worker(threading.Thread):

    def __init__(self, url, output, lock):
        super(Worker, self).__init__()
        self.url = url
        self.output = output
        self.lock = lock

    def run(self):
        while True:
            try:
                self.work()
                break
            except:
                continue

    def work(self):
        with self.lock:
            resp = requests.get(self.url)
            with open(self.output + ".html", "wb") as f:
                f.write(resp.text)
                print("{}".format(resp.url.split('/')[-1]))


class Controller(threading.Thread):

    def __init__(self, prefix, subejctList, outputDir, lock):
        super(Controller, self).__init__()
        self.prefix = prefix
        self.subejctList = subejctList
        self.outputDir = outputDir
        self.lock = lock

        if not os.path.exists(outputDir):
            os.mkdir(outputDir)
            print("Created directory {}".format(outputDir))

    def run(self):
        for code in self.subejctList:
            with self.lock:
                job = Worker(
                    self.prefix + code,
                    os.path.join(self.outputDir, code.strip()),
                    self.lock
                )
                job.start()


def main():
    parser = argparse.ArgumentParser(description="Fine Scraper")
    parser.add_argument('-n', help='task number', type=int, default=10)
    parser.add_argument('-l', help='subject list file', type=open, required=True)
    parser.add_argument('-p', '--prefix', help='url prefix', required=True)
    parser.add_argument('-o', help='output directory', default='./temp')

    args = parser.parse_args()

    # test
    # prefix = 'https://handbook.unimelb.edu.au/view/2014/'
    # args = parser.parse_args(['-l', 'subjects', '-p', prefix])
    # print(args)

    lock = threading.Semaphore(args.n + 1)

    boss = Controller(args.prefix, args.l, args.o, lock)
    boss.start()
    boss.join()


if __name__ == '__main__':
    main()
