#!/usr/bin/env python
import os
import re
import sys
import logging

from bs4 import BeautifulSoup
from xbook.ajax.models import Subject, SubjectPrereq, NonallowedSubject
# from utils.prerequisite_parser import PrerequisiteParser

path = os.path
BASE_DIR = path.dirname(path.abspath(__file__))
TEMP = path.join(BASE_DIR, "subjectPages")
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

    def prereq_code(self):
        return set(Processor.code_regex.findall(self.prereq))

    def nonallowed_code(self):
        return set(Processor.code_regex.findall(self.nonallowed))

    def prerequisite(self):
        return PrerequisiteParser().parse(self.prereq)

    def pre_subjects_codes(self):
        return map(lambda x: x.split()[0], self.pre_subjects_titles)

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


def process_subject():
    files = os.listdir(TEMP_DIR)
    for f in files:
        logging.info("Adding: " + f)
        p = Processor(f)

        new_values = {
            "name" :p.name,
            "code" :p.code,
            "credit" :float(p.credit or 0),
            "commence_date" :p.commencement_date,
            "time_commitment" :p.time_commitment,
            "overview" :p.overview,
            "objectives" :p.objectives,
            "assessment" :p.ass,
            "link" :p.url,
            "corequisite" :p.corequisite,
            "prerequisite" :p.prereq
        }

        s = Subject.objects.update_or_create(
            code=p.code, defaults=new_values
        )


def process_prereq():
    files = os.listdir(TEMP_DIR)
    for f in files:
        logging.info("Adding requisite for: " + f)
        p = Processor(f)
        s = Subject.objects.get(code=p.code)
        for qcode in p.prereq_code():
            try:
                q = Subject.objects.get(code=qcode)
                preq = SubjectPrereq(subject=s, prereq=q)
                preq.save()
            except:
                continue


def process_nonallowed():
    files = os.listdir(TEMP_DIR)
    for f in files:
        logging.info("Adding nonallowed for: " + f)
        p = Processor(f)
        s = Subject.objects.get(code=p.code)
        for qcode in p.nonallowed_code():
            try:
                q = Subject.objects.get(code=qcode)
                na = NonallowedSubject(subject=s, non_allowed=q)
                na.save()
            except:
                continue


def clear_old_subjects_relationships():
    logging.info("Clearing old nonallowed relationships")
    NonallowedSubject.objects.all().delete()

    logging.info("Clearing old requisite relationships")
    SubjectPrereq.objects.all().delete()

    logging.info("Finished clearing old subjects relationships")


def update_subjects():
    logging.info("Processing subjects.")
    process_subject()

    logging.info("Adding requisites.")
    process_prereq()

    logging.info("Adding nonallowed.")
    process_nonallowed()

    logging.info("Done.")


def setup_logger():
    format = "%(asctime)s %(levelname)s: %(message)s"
    date_format = "%d/%m/%Y %H:%M:%S"
    logging.basicConfig(format=format, level=logging.INFO, datefmt=date_format)


def update(delete_old=True):
    setup_logger()
    clear_old_subjects_relationships()
    update_subjects()


if __name__ == '__main__':
    # p = Processor("COMP30018.html")
    # print p
    print TEMP_DIR

def test_process(file="COMP30018.html"):
    p = Processor(file)
    print p
