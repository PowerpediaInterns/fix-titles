# imports
import pywikibot
import urllib3
import requests

import re
from collections import namedtuple

# disable warning when accessing http
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# constants
REFERENCE_PAGE = "Powerpedia:Fix Titles Bot Last Page"
PAGES_TO_GO_THROUGH = 25
title_search = re.compile(r"^(=+)([^=]*)(=+)[ ]?$")
Title = namedtuple("Title", ["name", "level"])

def print_list(alist):
    print('[')
    for i in alist:
        print(f"\t{i},")
    print(']')

class FixTitlesBot:
    '''
    Fixes titles that are of the wrong hierarchy.
    Correctly ordered titles of level n
    should be nested directly under a title of level n - 1.
    '''
    def __init__(self, site: pywikibot.site.APISite, reference_page_title: str):
        self.site = site
        self.api_url = site.protocol() + "://" + site.hostname() + site.apipath()
        self.reference_page_title = reference_page_title
    
    def _get_page_text(self, page_name: str) -> [str]:
        '''
        Gets the text for a page. Returns it as a list of lines.
        '''
        page = pywikibot.Page(self.site, page_name)
        page_lines = page.text.split('\n')
        return page_lines

    def _get_title(self, line: str) -> Title or None:
        '''
        Finds the title and returns it, or returns None.
        '''
        # search for title
        m = title_search.search(line)

        if m is None:
            return m

        # figure out the level
        start_level = len(m.group(1))
        end_level = len(m.group(3))
        true_level = min(start_level, end_level)

        # parse out the name
        true_name = m.group(0)[true_level:-true_level]

        # return the Title object
        return Title(name=true_name, level=true_level - 1)
    
    def _get_title_text(self, t: Title):
        '''
        From a Title, gives the text of the Title.
        '''
        return "=" * t.level + t.name + "=" * t.level

    def _fix_titles(self, page_name: str) -> None:
        '''
        Fixes all titles on the given page.
        '''
        # get page text
        page_lines = self._get_page_text(page_name)

        # keep track of current title hierarchy
        titles = []

        # loop through page text
        for line in page_lines:
            # figure out if a line has a title in it
            t = self._get_title(line)
            if t is not None:
                titles.append(t)

        # fix titles as needed
        new_titles = self._full_fix(titles)

        # make changes as needed
        if new_titles != titles:
            page = pywikibot.Page(self.site, page_name)

            for i in range(len(titles)):
                old_text = self._get_title_text(titles[i])
                new_text = self._get_title_text(new_titles[i])
                page.text = page.text.replace(old_text, new_text)

            
            page.save("Fix titles")

    def _semi_fix(self, title_list):
        '''
        Runs one fix on a list of titles.
        '''
        fixed_titles = []
        title_index = 0
        prev_level = 0

        title = lambda: title_list[title_index]

        while title_index < len(title_list):
            current_level = title().level

            if prev_level is not None and current_level > prev_level + 1:
                while title_index < len(title_list):
                    if title().level == prev_level:
                        break
                    fixed_titles.append(Title(name=title().name, level=title().level - 1))
                    title_index += 1
                else:
                    continue
                
            fixed_titles.append(Title(name=title().name, level=title().level))
            prev_level = current_level
            title_index += 1
        
        return fixed_titles

    def _full_fix(self, title_list):
        '''
        Runs a series of fixes on a list of titles.
        '''
        # preceding fixes
        title_list = self.first_title_fix(self.level_zero_fix(title_list))

        # primary level fixes
        while True:
            new_titles = self._semi_fix(title_list)
            if new_titles == title_list:
                break
            else:
                title_list = new_titles
        
        return new_titles
    
    def level_zero_fix(self, titles):
        new_titles = []

        for title in titles:
            if title.level == 0:
                # we need to increase all titles
                for title in titles:
                    new_titles.append(Title(title.name, title.level + 1))
        
        return new_titles if new_titles else titles

    def first_title_fix(self, titles):
        if titles and titles[0].level != 1:
            return [Title(name=titles[0].name, level=1)] + titles[1:]
        else:
            return titles
        


    def get_page_start(self) -> str:
        '''
        Returns the page that this bot is supposed to start editing from,
        according to this bot's reference page. 
        '''
        page = pywikibot.Page(self.site, self.reference_page_title)
        return page.text.split('\n')[0]
    
    def set_page_start(self, new_start: str) -> None:
        '''
        Sets the page that this bot will start from next to the string given.
        '''
        page = pywikibot.Page(self.site, self.reference_page_title)
        page.text = new_start
        page.save("Store new page from last execution.")

    def pages_from(self, start_point: str) -> "page generator":
        '''
        Returns a generator with 25 pages starting from
        the given page.
        '''
        my_session = requests.Session()

        api_arguments= {
            "action": "query",
            "format": "json",
            "list": "allpages",
            "apfrom": start_point,
            "aplimit": PAGES_TO_GO_THROUGH
        } 

        request = my_session.get(url=self.api_url, params=api_arguments, verify=False)
        data = request.json()

        pages = data["query"]["allpages"]
        return pages

    def run(self) -> None:
        '''
        Runs the bot on a certain number of pages.
        Records the last page the bot saw on a certain Mediawiki page.
        '''
        start_page_title = self.get_page_start()
        last_page_seen = ""

        pages_to_run = self.pages_from(start_page_title)

        for page in pages_to_run:
            last_page_seen = page['title']
            self._fix_titles(last_page_seen)
        
        if len(list(pages_to_run)) < PAGES_TO_GO_THROUGH:
            # if we hit the end, then loop back to beginning
            self.set_page_start("")
        else:
            # otherewise, just record the last page seen
            self.set_page_start(last_page_seen)



if __name__ == "__main__":
    FixTitlesBot(
        site=pywikibot.Site(),
        reference_page_title=REFERENCE_PAGE
    ).run()
