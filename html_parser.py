import os
import re
import sys

from bs4 import BeautifulSoup
from xbook.ajax.models import Subject, SubjectPrereq, NonallowedSubject
# from utils.prerequisite_parser import PrerequisiteParser

TEMP = "E:/Projects/subjectPages/subjectPages/"

class Processor:
    PREFIX = "https://handbook.unimelb.edu.au/view/2014/"
    CODE_REGEX = re.compile("[A-Z]{4}\d{5}")

    def __init__(self, filename):
        with open(TEMP + filename) as f:
            self.soup = BeautifulSoup(f)
            self.url = self.PREFIX + filename[:-5]
            self.title = self.soup.select("#content")[0].h2.string
            self.code = self.title.split()[0]
            try:
                commencementTemp = self.soup.find(
                    text=re.compile(r".*This subject commences in the following study period/s:.*")).parent
                self.commencementDate = self.__join_commence_dates(re.split("<br>", str(commencementTemp)))
            except:
                self.commencementDate = "Not Offered this year"
            self.timeCommitment = ''.join([x.encode('utf-8') for x in self.soup.find("th",
                                                                                     text="Time Commitment:").next_sibling.next_sibling.contents])
            if self.timeCommitment[-5:] == "</br>":
                self.timeCommitment = self.timeCommitment[:-5]
            try:
                self.corequisite = ''.join(map(str, self.soup.find("th",
                                                                   text="Corequisites:").next_sibling.next_sibling.next_element.next_element.contents))
            except:
                self.corequisite = ''.join(
                    map(str, self.soup.find("th", text="Corequisites:").next_sibling.next_sibling.contents))
            self.overview = ''.join([x.encode('utf-8') for x in self.soup.find("span",
                                                                               text="Subject Overview:").parent.next_sibling.next_sibling.contents])
            self.objectives = ''.join([x.encode('utf-8') for x in
                                       self.soup.find("th", text="Objectives:").next_sibling.next_sibling.contents])
            self.name = " ".join(self.title.split()[1:])
            self.credit = self.soup.find("th", text="Credit Points:").next_sibling.next_sibling.string
            self.ass = ''.join([x.encode('utf-8') for x in
                                self.soup.find("th", text="Assessment:").next_sibling.next_sibling.contents])
            self.prereq = ''.join(map(str, self.soup.find("th", text="Prerequisites:").next_sibling.next_sibling.contents))
            self.__clean_prerequisite_link()
            self.nonallowed = ''.join(
                map(str, self.soup.find("th", text="Non Allowed Subjects:").next_sibling.next_sibling.contents))

    def prereq_code(self):
        return set(self.CODE_REGEX.findall(self.prereq))

    def nonallowed_code(self):
        return set(self.CODE_REGEX.findall(self.nonallowed))

    def prerequisite(self):
        return PrerequisiteParser().parse(self.prereq)

    def pre_subjects_codes(self):
        return map(lambda x: x.split()[0], self.pre_subjects_titles)

    def __join_commence_dates(self, commenceList):
        commenceDates = ''
        for item in commenceList:
            if re.search(r"Summer Term|Semester| - Taught on campus\.| - Taught online/distance\.", item):
                commenceDates += re.sub(r"</?br/?>", r"", item) + "<br>"
        return commenceDates[:-4]

    def __clean_prerequisite_link(self):
        self.prereq = re.sub(r"</?a[^>]*>", r"", self.prereq)

    def __str__(self):

        return "Code: " + self.code \
               + "\n\nName: " + self.name \
               + "\n\nTitle: " + self.title \
               + "\n\nCredit Point: " + self.credit \
               + "\n\nCommencement Date: " + self.commencementDate \
               + "\n\nCorequisite: " + self.corequisite \
               + "\n\nTime Commitment: " + self.timeCommitment \
               + "\n\nOverview: " + self.overview \
               + "\n\nObjectives: " + self.objectives \
               + "\n\nAssessments: " + self.ass \
               + "\n\nPrerequisites: " + self.prereq \
               + "\n\nNonallowed subjects: " + self.nonallowed


def process_subject():
    files = os.listdir(TEMP)
    for f in files:
        sys.stderr.write(f + "\n")
        p = Processor(f)
        s = Subject(
            name=p.name,
            code=p.code,
            credit=float(p.credit or 0),
            commence_date=p.commencementDate,
            time_commitment=p.timeCommitment,
            overview=p.overview,
            objectives=p.objectives,
            assessment=p.ass,
            link=p.url,
            corequisite=p.corequisite,
            prerequisite=p.prereq
        )
        s.save()


def process_prereq():
    files = os.listdir(TEMP)
    for f in files:
        sys.stderr.write(f + "\n")
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
    files = os.listdir(TEMP)
    for f in files:
        sys.stderr.write(f + "\n")
        p = Processor(f)
        s = Subject.objects.get(code=p.code)
        for qcode in p.nonallowed_code():
            try:
                q = Subject.objects.get(code=qcode)
                na = NonallowedSubject(subject=s, non_allowed=q)
                na.save()
            except:
                continue


if __name__ == '__main__':
    p = Processor("COMP30018.html")
    print p