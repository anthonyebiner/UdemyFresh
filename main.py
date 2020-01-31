import requests
import time
import json
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium import webdriver

import auths


class Review:
    def __init__(self, review_dict: dict) -> None:
        """
        Initializes a review
        :param review_dict: dictionary produced by Udemy get reviews call
        """
        with open('reviews.csv', 'r') as file:
            self.fresh_reviews = file.read()
        self.id = review_dict['id']
        self.name = review_dict['user']['title']
        self.course_title = review_dict['course']['title']
        self.course_id = review_dict['course']['id']
        self.stars = review_dict['rating']
        self.created = review_dict['created']
        self.content = review_dict['content']
        self.response = review_dict['response']

    def freshen(self, session: requests.Session) -> bool:
        """
        Attempts to send a review to FreshDesk
        :rtype: bool
        :return: True if the review is sent, false otherwise
        :param session: requests.Session
        """
        if self.content and str(self.id) not in self.fresh_reviews:
            print('sending ticket')
            ticket = {
                'name': self.name,
                'subject': str(self.course_title) + ' Review / ' + self.name + ' / ' + str(
                    self.stars) + ' Stars / ' + str(self.id) + ' / ' + str(self.course_id),
                'description': self.content,
                'phone': str(self.id),
                'priority': 1,
                'status': 2,
                'group_id': 2043001631427,
                'tags': ['Review', str(self.stars) + ' stars'],
            }

            headers = {'Content-Type': 'application/json'}
            r = session.post("https://" + auths.domain + ".freshdesk.com/api/v2/tickets", auth=(auths.fresh_api, 'x'),
                             headers=headers, data=json.dumps(ticket))
            print(r)

            if r.status_code == 201:
                with open('reviews.csv', 'a') as file:
                    file.write(str(self.id) + '\n')
                return True
            else:
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                print(r)
                print(r.content)
                print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                return False
        else:
            return False


class UdemyReviews:
    def __init__(self, browser: webdriver.Firefox) -> None:
        """
        Initializes Udemy / FreshDesk. Gets Udemy Authkey through selenium.
        :param browser: A firefox webdriver
        """
        self.session = requests.Session()
        self.browser = browser
        self.browser.get('https://www.udemy.com/join/login-popup/?next=/instructor/performance/reviews/?unresponded=1')
        WebDriverWait(self.browser, 25).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#email--1"))).send_keys(auths.udemy_user)
        self.browser.find_element_by_css_selector('#id_password').send_keys(auths.udemy_pass)
        self.browser.find_element_by_css_selector('#submit-id-submit').click()
        time.sleep(3)
        cookies = self.browser.get_cookies()
        self.browser.close()
        self.browser.quit()

        for token in cookies:
            if token['name'] == 'access_token':
                self.access_token = token['value']
                print('access: ' + token['value'])
            elif token['name'] == 'csrftoken':
                self.csrf = token['value']
                print('csrf: ' + token['value'])

        self.udemy_auth = 'Bearer ' + self.access_token
        self.reviews_post = {'Host': 'www.udemy.com',
                             'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:72.0) Gecko/20100101 Firefox/72.0',
                             'Accept': 'application/json, text/plain, */*', 'Accept-Language': 'en-US,en;q=0.5',
                             'Accept-Encoding': 'gzip, deflate, br',
                             'Content-Type': 'application/json;charset=utf-8', 'X-Requested-With': 'XMLHttpRequest',
                             'Content-Length': '163', 'Origin': 'https://www.udemy.com', 'Connection': 'keep-alive',
                             'Referer': 'https://www.udemy.com/instructor/performance/reviews/?page_size=100%2F%3Funresponded%3D1%2F&unresponded=1',
                             'TE': 'Trailers',
                             'Authorization': self.udemy_auth}

    @staticmethod
    def review_dict_to_obj(review_dict: dict) -> Review:
        """
        Creates a Review from a dictionary of its attributes
        :param review_dict: dictionary produced by Udemy get reviews call
        :return: A Review object
        """
        return Review(review_dict)

    def get_reviews(self, num_reviews: int = 50, page: int = 1) -> list:
        """
        Get a dictionary of Udemy reviews
        :param num_reviews: The number of reviews on the page to get
        :param page: The page of the reviews to get
        :return: A dictionary of Udemy reviews
        """
        reviews_response = self.session.get(
            'https://www.udemy.com/api-2.0/users/me/taught-courses-reviews/?page=' + str(page) + '&page_size=' + str(
                num_reviews) + '&ordering=-user_modified&fields[course_review]=@default,course,response,survey_answers&fields[user]=id,title,display_name,initials,url&fields[course]=id,avg_rating,rating,url,title,num_reviews_recent,features,visible_instructors&fields[course_feature]=reviews_responses_create&fields[course_review_response]=id,content,user,modified,created&update_last_checked_reviews_time=0&unresponded=1',
            headers={'Authorization': self.udemy_auth})
        print('Getting Reviews')
        print(reviews_response)
        if reviews_response.status_code == 503:
            print(reviews_response.content)
            return 503
        return reviews_response.json()

    def udemy_to_fresh(self, total: int = 10, at_once: int = 50) -> None:
        """
        Add a number of reviews to FreshDesk from Udemy
        :param total: The total number of Udemy reviews to add to FreshDesk
        :param at_once: The number of Udemy Reviews per page
        """
        page = 1
        num_freshened = 0
        while True:
            print(page)
            review_response = self.get_reviews(num_reviews=at_once, page=page)
            if review_response == 503:
                print('503 response')
                page += 1
                time.sleep(2)
                continue
            reviews = review_response['results']
            for review in reviews:
                if num_freshened >= total:
                    break
                review = self.review_dict_to_obj(review)
                if review.freshen(self.session):
                    num_freshened += 1
            time.sleep(1)
            page += 1
            if num_freshened >= total:
                break

    def get_review_response(self, ticket_id: int) -> str:
        """
        Get the response to a Udemy review to be posted
        :param ticket_id: The id of the ticket
        :return: Last posted response. If none posted, None.
        """
        conversations = self.session.get(
            'https://' + auths.domain + '.freshdesk.com/api/v2/tickets/' + str(ticket_id) + '/conversations',
            auth=(auths.fresh_api, 'x'))
        if conversations.json():
            response = list(conversations.json())[-1]['body_text']
            return response
        else:
            return

    def get_tickets(self, limit: int) -> list:
        """
        Get all the responses that need to be sent to Udemy
        :param limit: The maximum number of responses to send to Udemy
        :return: A list of the responses to be sent
        """
        tickets = self.session.get(
            'https://' + auths.domain + '.freshdesk.com/api/v2/search/tickets?query="group_id:2043001631427%20AND%20status:5"',
            auth=(auths.fresh_api, 'x')).json()['results']
        review_responses = []
        num = 1
        for ticket in tickets:
            review_responses.append({'ticket_id': ticket['id'], 'user_id': ticket['subject'].split('/')[-2].strip(),
                                     'course_id': ticket['subject'].split('/')[-1].strip(),
                                     'response': self.get_review_response(ticket['id'])})
            num += 1
            if num >= limit:
                break
        return review_responses

    def fresh_to_udemy(self, limit: int) -> None:
        """
        Send a number of FreshDesk responses to Udemy
        :param limit: The maximum number of responses to sent to Udemy
        """
        print('Fresh to Udemy')
        responses = self.get_tickets(limit)
        for response in responses:
            if response['response']:
                request_body = {'content': str(response['response'])}
                url = 'https://www.udemy.com/api-2.0/courses/' + str(response['course_id']) + '/reviews/' + str(
                    response['user_id']) + '/responses'
                r = self.session.post(url, headers=self.reviews_post, data=json.dumps(request_body))
                if r.status_code == 201:
                    print('Response Posted')
                    r = self.session.delete(
                        'https://' + auths.domain + '.freshdesk.com/api/v2/tickets/' + str(response['ticket_id']),
                        auth=(auths.fresh_api, 'x'))
                    if r.status_code == 204:
                        print('Deleted')
                    else:
                        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                        print(r)
                        print(r.content)
                        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                else:
                    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
                    print(r)
                    print(r.content)
                    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
