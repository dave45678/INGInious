# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2015 Université Catholique de Louvain.
#
# This file is part of INGInious.
#
# INGInious is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INGInious is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with INGInious.  If not, see <http://www.gnu.org/licenses/>.
""" A custom Submission Manager that removes exceeding submissions """
import pymongo
from frontend.common.submission_manager import SubmissionManager


class LTISubmissionManager(SubmissionManager):
    """ A custom Submission Manager that removes exceeding submissions """
    def __init__(self, job_manager, user_manager, database, gridfs, hook_manager, max_submissions):
        self._max_submissions = max_submissions
        super(LTISubmissionManager, self).__init__(job_manager, user_manager, database, gridfs, hook_manager)

    def add_job(self, task, inputdata, debug=False):
        retval = super(LTISubmissionManager, self).add_job(task, inputdata, debug)
        self._delete_exceeding_submissions(self._user_manager.session_username(), task.get_course_id(), task.get_id())
        return retval

    def _delete_exceeding_submissions(self, username, course_id, task_id):
        """ Deletes exceeding submissions from the database, to keep the database relatively small """

        if self._max_submissions <= 0:
            return
        tasks = list(self._database.submissions.find({"username": username, "courseid": course_id, "taskid": task_id},
                                                     projection=["_id", "status", "result", "grade"],
                                                     sort=[('submitted_on', pymongo.DESCENDING)]))

        # Find the best "status"="done" and "result"="success"
        idx_best = -1
        for idx, val in enumerate(tasks):
            if val["status"] == "done" and val["result"] == "success":
                if idx_best == -1 or tasks[idx_best]["grade"] < val["grade"]:
                    idx_best = idx

        # List the entries to keep
        to_keep = set()

        # Always keep the best submission
        if idx_best != -1:
            to_keep.add(tasks[idx_best]["_id"])

        # Always keep running submissions
        for val in tasks:
            if val["status"] == "waiting":
                to_keep.add(val["_id"])

        while len(to_keep) < self._max_submissions and len(tasks) > 0:
            to_keep.add(tasks.pop()["_id"])

        to_delete = {val["_id"] for val in tasks}.difference(to_keep)
        self._database.submissions.delete_many({"_id": {"$in": list(to_delete)}})