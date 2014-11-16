#!/usr/bin/env python
import os
import re
import sys
import logging
import json
import requests

from bs4 import BeautifulSoup
from xbook.ajax.models import Subject, SubjectPrereq, NonallowedSubject
# from utils.prerequisite_parser import PrerequisiteParser

path = os.path
BASE_DIR = path.dirname(path.abspath(__file__))
TEMP = path.join(BASE_DIR, "temp")
TEMP_DIR = path.join(TEMP, "")


class Processor:
    PREFIX = "https://handbook.unimelb.edu.au/view/2015/"
    code_regex = re.compile(r"[A-Z]{4}\d{5}")
    semester_regex = re.compile(r"Summer Term|Semester| - Taught on campus\.| - Taught online/distance\.")
    anchor_regex = re.compile(r"<(/?)a[^>]*>")

    def __init__(self, filename):
        with open(TEMP_DIR + filename) as f:
            self.soup = BeautifulSoup(f)

            self.url = self.PREFIX + filename[:-5]

            self.title = self.soup.select("#content")[0].h2.string

            self.code = self.title.split()[0]

            try:
                commencement_temp = self.soup.find(
                    text=re.compile(r".*This subject commences in the following study period/s:.*")
                ).parent
                self.commencement_date = self.__join_commence_dates(re.split("<br>", str(commencement_temp)))
            except:
                self.commencement_date = "Not Offered this year"

            self.time_commitment = ''.join([
                x.encode('utf-8') for x in self.soup.find(
                    "th",
                    text="Time Commitment:"
                ).next_sibling.next_sibling.contents
            ])

            if self.time_commitment[-5:] == "</br>"  :
                self.time_commitment = self.time_commitment[:-5]
            try:
                self.corequisite = ''.join(map(str, self.soup.find(
                        "th", text="Corequisites:"
                    ).next_sibling.next_sibling.next_element.next_element.contents))
            except:
                self.corequisite = ''.join(map(
                    lambda input_soup: Processor.anchor_regex.sub(r"<\1p>", str(input_soup)),
                    self.soup.find("th", text="Corequisites:").next_sibling.next_sibling.contents
                ))

            self.overview = ''.join([x.encode('utf-8') for x in self.soup.find(
                    "span", text="Subject Overview:"
                ).parent.next_sibling.next_sibling.contents])

            self.objectives = ''.join([x.encode('utf-8') for x in
               self.soup.find("th", text="Learning Outcomes:").next_sibling.next_sibling.contents])

            self.name = " ".join(self.title.split()[1:])

            self.credit = self.soup.find("th", text="Credit Points:").next_sibling.next_sibling.string

            self.ass = ''.join([x.encode('utf-8') for x in
                self.soup.find("th", text="Assessment:").next_sibling.next_sibling.contents])

            self.prereq = ''.join(map(str, self.soup.find("th", text="Prerequisites:").next_sibling.next_sibling.contents))

            self.__clean_prerequisite_link()

            self.nonallowed = ''.join(
                map(str, self.soup.find("th", text="Non Allowed Subjects:").next_sibling.next_sibling.contents))

    def __join_commence_dates(self, commence_list):
        commence_dates = ''
        for item in commence_list:
            if Processor.semester_regex.search(item):
                commence_dates += re.sub(r"</?br/?>", r"", item) + "<br>"
        return commence_dates[:-4]

    def __clean_prerequisite_link(self):
        self.prereq = Processor.anchor_regex.sub(r"<\1p>", self.prereq)

    def __str__(self):
        return "Code: " + self.code \
               + "\n\nName: " + self.name \
               + "\n\nTitle: " + self.title \
               + "\n\nCredit Point: " + self.credit \
               + "\n\nCommencement Date: " + self.commencement_date \
               + "\n\nCorequisite: " + self.corequisite \
               + "\n\nTime Commitment: " + self.time_commitment \
               + "\n\nOverview: " + self.overview \
               + "\n\nObjectives: " + self.objectives \
               + "\n\nAssessments: " + self.ass \
               + "\n\nPrerequisites: " + self.prereq \
               + "\n\nNonallowed subjects: " + self.nonallowed

    def to_dict(self):
        return {
            "name": self.name,
            "code": self.code,
            "credit": float(self.credit or 0),
            "commence_date": self.commencement_date,
            "time_commitment": self.time_commitment,
            "overview": self.overview,
            "objectives": self.objectives,
            "assessment": self.ass,
            "link": self.url,
            "corequisite": self.corequisite,
            "prerequisite": self.prereq,
            "nonallowed": self.nonallowed
        }

    @staticmethod
    def subject_wo_nonallowed(subject):
        subject_wo_nonallowed = dict(subject)
        del subject_wo_nonallowed["nonallowed"]
        return subject_wo_nonallowed

    @staticmethod
    def prereq_code(subject):
        return set(Processor.code_regex.findall(subject["prerequisite"]))

    @staticmethod
    def nonallowed_code(subject):
        return set(Processor.code_regex.findall(subject["nonallowed"]))


def process_subject(write_to_db, processed_subjects={}):
    if write_to_db:
        for subject_code in processed_subjects:
            logging.info("Saving: " + subject_code)
            s = Subject.objects.update_or_create(
                code=subject_code,
                defaults=Processor.subject_wo_nonallowed(processed_subjects[subject_code])
            )
    else:
        files = os.listdir(TEMP_DIR)
        for f in files:
            logging.info("Processing: " + f)
            p = Processor(f)

            new_values = p.to_dict()

            processed_subjects[p.code] = new_values

    return processed_subjects


def process_prereq(processed_subjects):
    for subject_code in processed_subjects:
        logging.info("Adding requisite for: " + subject_code)
        s = Subject.objects.get(code=subject_code)
        for qcode in Processor.prereq_code(processed_subjects[subject_code]):
            try:
                q = Subject.objects.get(code=qcode)
                SubjectPrereq.objects.get_or_create(subject=s, prereq=q)
            except:
                logging.warning("Cannot save prerequisite relationship: " + subject_code + " - " + qcode)
                continue


def clear_old_subjects_relationships():
    logging.info("Clearing old nonallowed relationships")
    NonallowedSubject.objects.all().delete()

    logging.info("Clearing old requisite relationships")
    SubjectPrereq.objects.all().delete()

    logging.info("Finished clearing old subjects relationships")


def update_relationships(processed_subjects):
    logging.info("Adding requisites.")
    process_prereq(processed_subjects)

    logging.info("Done.")


def write_json(processed_subjects):
    logging.info("Writting processed subjects dictionary as json.")
    f = open(TEMP_DIR + "processed.json", "w")
    f.write(json.dumps(processed_subjects))
    f.close()


def read_json(address, is_url=True):
    processed_subjects = {}
    if is_url:
        response = requests.get(address)
        processed_subjects = json.loads(response.content)
    else:
        f = open(address)
        content = f.read()
        f.close()
        processed_subjects = json.loads(content)
    return processed_subjects


def setup_logger():
    format = "%(asctime)s %(levelname)s: %(message)s"
    date_format = "%d/%m/%Y %H:%M:%S"
    logging.basicConfig(format=format, level=logging.INFO, datefmt=date_format)


def update_or_output(delete_old=False, write_to_db=False):
    setup_logger()

    if delete_old:
        clear_old_subjects_relationships()

    processed_subjects = process_subject(write_to_db)

    if not write_to_db:
        write_json(processed_subjects)
        logging.info("New subjects has been output to a json file.")
    else:
        update_relationships(processed_subjects)


def read_and_update(address, is_url=True):
    setup_logger()

    processed_subjects = read_json(address, is_url)
    process_subject(True, processed_subjects=processed_subjects)
    update_relationships(processed_subjects)


if __name__ == '__main__':
    # p = Processor("COMP30018.html")
    # print p
    print TEMP_DIR

def test_process(file="COMP30018.html"):
    p = Processor(file)
    print p
