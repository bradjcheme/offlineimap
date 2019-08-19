#!/usr/bin/python3

"""

Put into Public Domain, by Nicolas Sebrecht.

Make a new release.

"""

#TODO: announce: cc list on announce includes all testers
#TODO: announce: remove empty sections
#TODO: websitedoc up
#TODO: website branch not including all changes!


from os import system, path, rename
from datetime import datetime
from subprocess import check_call
import shlex
import time
from email import utils

from helpers import (
    MAILING_LIST, CACHEDIR, EDITOR, Git, OfflineimapInfo, Testers, User, run, goTo
)


__VERSION__ = "0.2"

SPHINXBUILD = 'sphinx-build'
DOCSDIR = 'docs'
CHANGELOG_MAGIC = '{:toc}'
WEBSITE_LATEST = "website/_data/latest.yml"

CHANGELOG_EXCERPT = "{}/changelog.excerpt.md".format(CACHEDIR)
CHANGELOG_EXCERPT_OLD = "{}.old".format(CHANGELOG_EXCERPT)
CHANGELOG = "Changelog.md"
ANNOUNCE_FILE = "{}/announce.txt".format(CACHEDIR)

WEBSITE_LATEST_SKEL = """# DO NOT EDIT MANUALLY: it is generated by the release script.
stable: v{stable}
"""

CHANGELOG_SKEL = """
### OfflineIMAP v{version} ({date})

#### Notes


This release was tested by:

{testersList}

#### Authors

{authorsList}

#### Features


#### Fixes


#### Changes



{commitsList}

"""

END_MESSAGE = """
Release is ready!
Make your checks and push the changes for both offlineimap and the website.
Announce template stands in '{announce}'.
Command samples to do manually:

- git push <remote> master next {new_version}
- python2 setup.py sdist && twine upload dist/* && rm -rf dist MANIFEST
- cd website
- git checkout master
- git merge {website_branch}
- git push <remote> master
- cd ..
- git send-email {announce}

...and write a Twitter message.
Have fun! ,-)
"""


class State(object):
    def __init__(self):
        self.master = None
        self.next = None
        self.website = None
        self.tag = None

    def setTag(self, tag):
        self.tag = tag

    def save(self):
        self.master = Git.getRef('master')
        self.next = Git.getRef('next')

    def saveWebsite(self):
        Git.chdirToRepositoryTopLevel()
        goTo('website')
        self.website = Git.getRef('master')
        goTo('..')

    def restore(self):
        Git.chdirToRepositoryTopLevel()
        try:
            Git.checkout('-f')
        except:
            pass
        # Git.checkout('master')
        # Git.resetKeep(self.master)
        # Git.checkout('next')
        # Git.resetKeep(self.next)

        if self.tag is not None:
            Git.rmTag(self.tag)

        if self.website is not None:
            if goTo('website'):
                Git.checkout(self.website)
                goTo('..')


class Changelog(object):
    def __init__(self):
        self.shouldUsePrevious = False

    def edit(self):
        return system("{} {}".format(EDITOR, CHANGELOG_EXCERPT))

    def update(self):
        # Insert excerpt to CHANGELOG.
        system("sed -i -e '/{}/ r {}' '{}'".format(
                CHANGELOG_MAGIC, CHANGELOG_EXCERPT, CHANGELOG
            )
        )
        # Remove trailing whitespaces.
        system("sed -i -r -e 's, +$,,' '{}'".format(CHANGELOG))

    def savePrevious(self):
        rename(CHANGELOG_EXCERPT, CHANGELOG_EXCERPT_OLD)

    def isPrevious(self):
        if path.isfile(CHANGELOG_EXCERPT_OLD):
            return True
        return False

    def showPrevious(self):
        output = run(shlex.split("cat '{}'".format(CHANGELOG_EXCERPT_OLD)))
        for line in output.splitlines():
            print(line.decode('utf-8')) # Weird to have to decode bytes here.

    def usePrevious(self):
        rename(CHANGELOG_EXCERPT_OLD, CHANGELOG_EXCERPT)
        self.shouldUsePrevious = True

    def usingPrevious(self):
        return self.shouldUsePrevious

    def writeExcerpt(self, version, date,
            testersList, authorsList, commitsList):

        with open(CHANGELOG_EXCERPT, 'w+') as fd:
            fd.write(CHANGELOG_SKEL.format(
                version=version,
                date=date,
                testersList=testersList,
                authorsList=authorsList,
                commitsList=commitsList,
            ))

    def getSectionsContent(self):
        dict_Content = {}

        with open(CHANGELOG_EXCERPT, 'r') as fd:
            currentSection = None
            for line in fd:
                line = line.rstrip()
                if line == "#### Notes":
                    currentSection = 'Notes'
                    dict_Content['Notes'] = ""
                    continue # Don't keep this title.
                elif line == "#### Authors":
                    currentSection = 'Authors'
                    dict_Content['Authors'] = ""
                    continue # Don't keep this title.
                elif line == "#### Features":
                    currentSection = 'Features'
                    dict_Content['Features'] = ""
                    continue # Don't keep this title.
                elif line == "#### Fixes":
                    currentSection = 'Fixes'
                    dict_Content['Fixes'] = ""
                    continue # Don't keep this title.
                elif line == "#### Changes":
                    currentSection = 'Changes'
                    dict_Content['Changes'] = ""
                    continue # Don't keep this title.
                elif line == "-- ":
                    break # Stop extraction.

                if currentSection is not None:
                    dict_Content[currentSection] += "{}\n".format(line)

        #TODO: cleanup empty sections.
        return dict_Content


class Announce(object):
    def __init__(self, version):
        self.fd = open(ANNOUNCE_FILE, 'w')
        self.version = version

    def setHeaders(self, messageId, date):
        self.fd.write("Message-Id: {}\n".format(messageId))
        self.fd.write("Date: {}\n".format(date))
        self.fd.write("From: Nicolas Sebrecht <nicolas.s-dev@laposte.net>\n")
        self.fd.write("To: {}\n".format(MAILING_LIST))
        self.fd.write(
            "Subject: [ANNOUNCE] OfflineIMAP v{} released\n".format(self.version))
        self.fd.write("\n")

        self.fd.write("""
OfflineIMAP v{version} is out.

Downloads:
  http://github.com/OfflineIMAP/offlineimap/archive/v{version}.tar.gz
  http://github.com/OfflineIMAP/offlineimap/archive/v{version}.zip

Pip:
  wget "https://raw.githubusercontent.com/OfflineIMAP/offlineimap/v{version}/requirements.txt" -O requirements.txt
  pip install -r ./requirements.txt --user git+https://github.com/OfflineIMAP/offlineimap.git@v{version}

""".format(version=self.version)
        )

    def setContent(self, dict_Content):
        self.fd.write("\n")
        for section in ['Notes', 'Authors', 'Features', 'Fixes', 'Changes']:
            if section in dict_Content:
                if section != "Notes":
                    self.fd.write("# {}\n".format(section))
                self.fd.write(dict_Content[section])
                self.fd.write("\n")
        # Signature.
        self.fd.write("-- \n")
        self.fd.write("Nicolas Sebrecht\n")

    def close(self):
        self.fd.close()


class Website(object):
    def updateUploads(self):
        req = ("add new archive to uploads/ on the website? "
            "(warning: checksums will change if it already exists)")
        if User.yesNo(req, defaultToYes=True) is False:
            return False
        if check_call(shlex.split("./docs/build-uploads.sh")) != 0:
            return exit(5)
        return True

    def updateAPI(self):
        req = "update API of the website? (requires {})".format(SPHINXBUILD)
        if User.yesNo(req, defaultToYes=True) is False:
            return False

        try:
            if check_call(shlex.split("{} --version".format(SPHINXBUILD))) != 0:
                raise RuntimeError("{} not found".format(SPHINXBUILD))
        except:
            print("""
Oops! you don't have {} installed?"
Cannot update the webite documentation..."
You should install it and manually run:"
  $ cd {}"
  $ make websitedoc"
Then, commit and push changes of the website.""".format(SPHINXBUILD, DOCSDIR))
            User.pause()
            return False

        Git.chdirToRepositoryTopLevel()
        if not goTo('website'):
            User.pause()
            return False
        if not Git.isClean:
            print("There is WIP in the website repository: stashing")
            Git.stash('WIP during offlineimap API import')

        goTo('..')
        return True

    def buildLatest(self, version):
        Git.chdirToRepositoryTopLevel()
        with open(WEBSITE_LATEST, 'w') as fd:
            fd.write(WEBSITE_LATEST_SKEL.format(stable=version))

    def exportDocs(self):
        if not goTo(DOCSDIR):
            User.pause()
            return

        if check_call(shlex.split("make websitedoc")) != 0:
            print("error while calling 'make websitedoc'")
            exit(3)

    def createImportBranch(self, version):
        branchName = "import-v{}".format(version)

        Git.chdirToRepositoryTopLevel()
        if not goTo("website"):
            User.pause()
            return

        Git.checkout(branchName, create=True)
        Git.add('.')
        Git.commit("update for offlineimap v{}".format(version))

        User.pause(
            "website: branch '{}' is ready for a merge in master!".format(
                branchName
            )
        )
        goTo('..')
        return branchName


class Release(object):
    def __init__(self):
        self.state = State()
        self.offlineimapInfo = OfflineimapInfo()
        self.testers = Testers()
        self.changelog = Changelog()
        self.websiteBranch = "NO_BRANCH_NAME_ERROR"


    def getVersion(self):
        return self.offlineimapInfo.getVersion()

    def prepare(self):
        if not Git.isClean():
            print("The git repository is not clean; aborting")
            exit(1)
        Git.makeCacheDir()
        Git.checkout('next')

    def requestVersion(self, currentVersion):
        User.request("going to make a new release after {}".format(currentVersion))

    def updateVersion(self):
        self.offlineimapInfo.editInit()

    def checkVersions(self, current, new):
        if new == current:
            print("version was not changed; stopping.")
            exit(1)

    def updateChangelog(self):
        if self.changelog.isPrevious():
            self.changelog.showPrevious()
            if User.yesNo("A previous Changelog excerpt was found. Use it?"):
                self.changelog.usePrevious()

        if not self.changelog.usingPrevious():
            date = datetime.now().strftime('%Y-%m-%d')
            testersList = ""
            testers = self.testers.getListOk()
            authorsList = ""
            authors = Git.getAuthorsList(currentVersion)

            for tester in testers:
                testersList += "- {}\n".format(tester.getName())
            for author in authors:
                authorsList += "- {} ({})\n".format(
                    author.getName(), author.getCount()
                )
            commitsList = Git.getCommitsList(currentVersion)
            date = datetime.now().strftime('%Y-%m-%d')
            self.changelog.writeExcerpt(
                newVersion, date, testersList, authorsList, commitsList
            )

        self.changelog.edit()
        self.changelog.update()

    def writeAnnounce(self):
        announce = Announce(newVersion)

        messageId = utils.make_msgid('release.py', 'laposte.net')
        nowtuple = datetime.now().timetuple()
        nowtimestamp = time.mktime(nowtuple)
        date = utils.formatdate(nowtimestamp)

        announce.setHeaders(messageId, date)
        announce.setContent(self.changelog.getSectionsContent())
        announce.close()

    def make(self):
        Git.add('offlineimap/__init__.py')
        Git.add('Changelog.md')
        commitMsg = "v{}\n".format(newVersion)
        for tester in self.testers.getListOk():
            commitMsg = "{}\nTested-by: {} {}".format(
                commitMsg, tester.getName(), tester.getEmail()
            )
        Git.commit(commitMsg)
        self.state.setTag(newVersion)
        Git.tag(newVersion)
        Git.checkout('master')
        Git.mergeFF('next')
        Git.checkout('next')

    def updateWebsite(self, newVersion):
        self.state.saveWebsite()
        website = Website()
        website.buildLatest(newVersion)
        res_upload = website.updateUploads()
        res_api = website.updateAPI()
        if res_api:
            res_export = website.exportDocs()
        if True in [res_upload, res_api, res_export]:
            self.websiteBranch = website.createImportBranch(newVersion)

    def getWebsiteBranch(self):
        return self.websiteBranch

    def after(self):
        for protectedRun in [self.testers.reset, self.changelog.savePrevious]:
            try:
                protectedRun()
            except Exception as e:
                print(e)

    def restore(self):
        self.state.restore()


if __name__ == '__main__':
    release = Release()
    Git.chdirToRepositoryTopLevel()

    try:
        release.prepare()
        currentVersion = release.getVersion()

        release.requestVersion(currentVersion)
        release.updateVersion()
        newVersion = release.getVersion()

        release.checkVersions(currentVersion, newVersion)
        release.updateChangelog()

        release.writeAnnounce()
        User.pause()

        release.make()
        release.updateWebsite(newVersion)
        release.after()

        websiteBranch = release.getWebsiteBranch()
        print(END_MESSAGE.format(
                announce=ANNOUNCE_FILE,
                new_version=newVersion,
                website_branch=websiteBranch)
        )
    except Exception as e:
        release.restore()
        raise
