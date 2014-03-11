#!/usr/bin/env python

from __future__ import print_function
from asana import asana
from collections import defaultdict
from optparse import OptionParser
from os import path

import os
import simplejson
import shutil

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
    projects_d = dict([(project["name"], project["id"]) for project in asana_api.list_projects(workspace_id)])
    if not project_name:
        __script_print("Available projects:\n" + "\n".join(projects_d.keys()))
        return None
    else:
        return projects_d[project_name]


def get_project_tasks(asana_api, project_id, copy_completed=False):
    completed = ""
    if not copy_completed:
        completed = "&completed_since=now"
    # use the link directly for performance issues
    # TODO: rewrite to proper method call once the pull request to asana repository is accepted
    return asana_api._asana('projects/{0}/tasks?include_archived=false&opt_expand=.{1}'.format(project_id, completed))
    # return [z for z in reversed([asana_api.get_task(x['id']) for x in asana_api.get_project_tasks(project_id)]) if copy_completed or not z['completed']]


def get_user_email(asana_api, user_id):
    return asana_api.user_info(user_id)['email']


def write_task(task, filename, creator, number=0, label=None, milestone=None, assignee=None):
    issue_dict = {
        "number": number,
        "title": "",
        "body": "",
        "created_at": None,
        "updated_at": None,
        "closed_at": None,
        "user": creator,
        "assignee": None,
        "milestone": milestone,
        "labels": label if label else [],
        "state": "open"
    }

    issue_dict["title"] = task['name']
    issue_dict["body"] = task["notes"]
    issue_dict["created_at"] = task["created_at"]
    issue_dict["updated_at"] = task["modified_at"]
    issue_dict["closed_at"] = task["completed_at"]
    if task["completed"]:
        issue_dict["state"] = "closed"
    task_assignee = None
    if task['assignee']:
        task_assignee = task['assignee']['name']
    issue_dict['assignee'] = assignee if assignee else task_assignee

    with open(filename, 'w+') as issue_file:
        simplejson.dump(issue_dict, issue_file)


def main():
    global __script_print
    __script_print = print
    global __verbose_print
    parser = OptionParser(usage="usage: %prog [options] AsanaAPIkey\nAsanaAPIkey can be found at https://app.asana.com/-/account_api")
    parser.add_option("-o", "--output", action="store", type="string", dest="directory_name", default=".", help="main directory name for output files")
    parser.add_option("-p", "--project", action="store", type="string", dest="project_name", help="asana project name to be used")
    parser.add_option("-w", "--workspace", action="store", type="string", dest="workspace_name", help="asana workspace name to be used")
    parser.add_option("-c", "--copy-completed", action="store_true", dest="copy_completed", default=False, help="copy completed tasks as well")
    parser.add_option("-n", "--number", action="store", type="int", dest="number", default=1, help="from what number should issues' ids start")
    parser.add_option("-q", "--quiet", action="store_false", dest="verbose", help="quiet mode")
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=True, help="verbose mode (default)")
    parser.add_option("-d", "--dictionary", action="store", type="string", dest="dictionary_file", default=None, help="file containing python dictionary for translating Asana users to Github users; "
                                                                                                                      "by default e-mail addresses from Asana are used in Github to search for users")
    parser.add_option("-u", "--user", action="store", type="string", dest="default_user", default=None, help="default name of user which should be user as creator of issue if "
                                                                                                             "dictionary look-up fails (by default it's going to be import requester's name)")
    parser.add_option("-m", "--milestone", action="store", type="string", dest="milestone", default=None, help="name of milestone to apply")
    parser.add_option("-l", "--label", action="store", type="string", dest="label", default=None, help='label to apply')
    parser.add_option("--clean", action="store_true", default=False, dest="clean", help="removes issues directory from the destination directory")
    options, args = parser.parse_args()
    options.directory_name = path.join(options.directory_name, 'issues')

    if options.verbose:
        __verbose_print = print

    if options.clean:
        if path.exists(options.directory_name):
            shutil.rmtree(options.directory_name)
            __verbose_print("Directory \"{0}\" cleaned ".format(options.directory_name))
        else:
            __verbose_print("Directory \"{0}\" not cleaned as it does not exist".format(options.directory_name))
        if not args:
            exit()

    if len(args) != 1:
        parser.error("Asana API key missing")

    asana_api = asana.AsanaAPI(args[0])
    number = options.number
    label = [] if not options.label else [options.label]

    __verbose_print("Looking through workspaces")
    workspace_id = get_workspace_id(asana_api, options.workspace_name)
    if not workspace_id:
        exit()
    __verbose_print("Workspace {0} found".format(options.workspace_name))

    __verbose_print("Looking through projects")
    project_id = get_project_id(asana_api, workspace_id, options.project_name)
    if not project_id:
        exit()
    __verbose_print("Project {0} found".format(options.project_name))

    __verbose_print("Getting list of tasks")
    tasks = get_project_tasks(asana_api, project_id, options.copy_completed)
    __verbose_print("Got {0} tasks".format(len(tasks)))

    if not path.exists(options.directory_name):
        os.makedirs(options.directory_name)

    if options.dictionary_file:
        __verbose_print("Getting user dictionnary from {0}".format(options.dictionary_file))
        with open(options.dictionary_file) as dict_f:
            text_d = dict_f.read()
            creator_dict = defaultdict(lambda: options.default_user, eval(text_d))
            assignee_dict = defaultdict(lambda: None, eval(text_d))
        __verbose_print("Dictionary read: {0}".format(text_d))
    else:
        creator_dict = defaultdict(lambda: options.default_user)
        assignee_dict = defaultdict(lambda: None)

    __verbose_print("Going through tasks")
    for task in reversed(tasks):
        __verbose_print("Writing task '" + task['name'] + "'")
        stories = asana_api.list_stories(task['id'])
        issue_dict = {
            "number": number,
            "title": "",
            "body": "",
            "created_at": None,
            "updated_at": None,
            "closed_at": None,
            "user": None,
            "assignee": None,
            "milestone": options.milestone,
            "labels": label,
            "state": "open"
        }
        issue_dict["title"] = task['name']
        issue_dict["body"] = task["notes"]
        issue_dict["created_at"] = task["created_at"]
        issue_dict["updated_at"] = task["modified_at"]
        issue_dict["closed_at"] = task["completed_at"]
        if task["completed"]:
            issue_dict["state"] = "closed"

        assignee = None
        if task['assignee']:
            assignee = assignee_dict[task['assignee']['name']]
            assignee = assignee if assignee else get_user_email(asana_api, task['assignee']['id'])  # last resort check - email address (Github falls back to importer if email is not in database

        creator = creator_dict[stories[0]["created_by"]["name"]]
        creator = creator if creator else get_user_email(asana_api, stories[0]["created_by"]["id"])  # last resort check - email address (Github falls back to importer if email is not in database
        write_task(task, path.join(options.directory_name, '{0}.json'.format(number)), creator, assignee=assignee, milestone=options.milestone, label=label, number=number)

        comments_list = []
        for story in stories[1:]:
            if story['type'] == 'comment':
                user = assignee_dict[story["created_by"]["name"]]
                user = user if user else get_user_email(asana_api, story["created_by"]["id"])  # last resort check - email address (Github falls back to importer if email is not in database
                __verbose_print("Adding comment by " + user)
                comments_list.append({"user": user, 'body': story['text'], 'created_at': story['created_at'], 'updated_at': None})

        with open(path.join(options.directory_name, '{0}.comments.json'.format(number)), 'w+') as comments_file:
            simplejson.dump(comments_list, comments_file)
        number += 1
    __verbose_print("Writing finished")

if __name__ == "__main__":
    main()