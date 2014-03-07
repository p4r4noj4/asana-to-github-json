#!/usr/bin/env python

from __future__ import print_function
from asana import asana
from optparse import OptionParser
from os import path
import simplejson


__verbose_print = lambda *a: None
__script_print = lambda *a: None  # will only print if used as script (important info, cannot be silenced)


def get_workspace_id(asana_api, workspace_name=None):

    workspaces_d = dict([(workspace["name"], workspace["id"]) for workspace in asana_api.list_workspaces()])
    if not workspace_name:
        __script_print("Available workspaces:\n" + "\n".join(workspaces_d.keys()))
        return None
    else:
        return workspaces_d[workspace_name]


def get_project_id(asana_api, workspace_id, project_name=None):
    pass


def get_project_tasks(asana_api, project_id):
    tasks = reversed(asana_api.get_project_tasks(project_id))
    pass


def main():
    global __script_print
    __script_print = print
    global __verbose_print
    parser = OptionParser(usage="usage: %prog [options] AsanaAPIkey\nAsanaAPIkey can be found at https://app.asana.com/-/account_api")
    parser.add_option("-o", "--output", action="store", type="string", dest="directory_name", default=".", help="main directory name for output files")
    parser.add_option("-p", "--project", action="store", type="string", dest="project_name", help="asana project name to be used")
    parser.add_option("-w", "--workspace", action="store", type="string", dest="workspace_name", help="asana workspace name to be used")
    parser.add_option("-c", "--completed", action="store_true", dest="copy_completed", default=False, help="copy completed tasks as well")
    parser.add_option("-n", "--number", action="store", type="int", dest="number", default=1, help="from what number should issues' ids start")
    parser.add_option("-q", "--quiet", action="store_false", dest="verbose", help="quiet mode")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=True, help="verbose mode (default)")
    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error("incorrect number of arguments")

    asana_api = asana.AsanaAPI(args[0])
    number = options.number

    if options.verbose:
        __verbose_print = print

    workspace_id = get_workspace_id(asana_api, options.workspace_name)
    if not workspace_id:
        exit()

    project_id = get_project_id(asana_api, workspace_id, options.project_name)

    tasks_ids = get_project_tasks(asana_api, project_id)

    assignee_dict = {}
    for t in tasks_ids:
        t_id = t['id']
        __verbose_print("Writing task '" + t['name'] + "'")
        task = asana_api.get_task(t_id)
        stories = asana_api.list_stories(t_id)
        issue_dict = {
            "number": number,
            "title": "",
            "body": "",
            "created_at": None,
            "updated_at": None,
            "closed_at": None,
            "user": None,
            "assignee": None,
            "milestone": None,
            "labels": [],
            "state": "open"
        }
        issue_dict["title"] = task['name']
        issue_dict["body"] = task["notes"]
        issue_dict["created_at"] = task["created_at"]
        issue_dict["updated_at"] = task["modified_at"]
        issue_dict["closed_at"] = task["completed_at"]
        if task["completed"]:
            issue_dict["state"] = "closed"

        if task['assignee'] and task['assignee']['name'] in assignee_dict:
            issue_dict['assignee'] = assignee_dict[task['assignee']['name']]
        if stories[0]["created_by"]["name"] in assignee_dict:
            issue_dict["user"] = assignee_dict[stories[0]["created_by"]["name"]]

        with open(path.join(options.directory_name, '{0}.json'.format(number)), 'w+') as issue_file:
            simplejson.dump(issue_dict, issue_file)

        comments_list = []
        for story in stories[1:]:
            if story['type'] == 'comment':
                user = assignee_dict[story["created_by"]["name"]] if story["created_by"]["name"] in assignee_dict else 'pdmvserv'
                __verbose_print("Adding comment by " + user)
                comments_list.append({"user": user, 'body': story['text'], 'created_at': story['created_at'], 'updated_at': None})

        with open(path.join(options.directory_name, '{0}.comments.json'.format(number)), 'w+') as comments_file:
            simplejson.dump(comments_list, comments_file)
        number += 1

if __name__ == "__main__":
    main()