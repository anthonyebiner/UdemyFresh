from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from main import UdemyReviews
from time import sleep

options = Options()
options.headless = False
driver = webdriver.Firefox(options=options)
test = UdemyReviews(driver)
while True:
    test.udemy_to_fresh(40)
    test.fresh_to_udemy(40)
    sleep(60)
    break

