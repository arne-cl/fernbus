#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Author: Arne Neumann

import argparse
from collections import namedtuple
import datetime
import re
import sys
import traceback
from utils import create_module_logger

from lxml import etree
from prettytable import PrettyTable
import dryscrape
from dryscrape.mixins import WaitMixin, WaitTimeoutError
import pudb

from fernbus.utils import create_module_logger, natural_sort_key


DEBUG = False
LOGGER = create_module_logger('main', filename='fernbus.log')
SEARCH_PAGE = 'https://www.busliniensuche.de/'
DELAY_MSG_REGEX = re.compile('Lade Busverbindungen')
COMMA_REGEX = re.compile(',')


# a Connection stores all the information about a single bus connection
Connection = namedtuple('Connection',
                        ('departure_date departure_time departure_stop '
                         'trip_duration number_of_stops '
                         'arrival_date arrival_time arrival_stop '
                         'price company'))


class BusliniensucheParsingError(Exception): pass


def create_browser_session(url=SEARCH_PAGE,
                           load_images=False):
    """
    creates a drysprace (webkit-based) browser session that enables us
    to scrape pages that need javascript to run correctly.

    Parameters
    ----------
    url : str
        the URL that the browser should connect to
    load_images : bool
        Iff true, loads images when retrieving a website (useful for debugging
        via screenshots)

    Returns
    -------
    browser_session : dryscrape.session.Session
        a browser session that can be used to run queries against
        the given website.
    """
    browser_session = dryscrape.Session()
    browser_session.set_attribute('auto_load_images', load_images)
    browser_session.visit(url) # connect to the search page
    LOGGER.debug('browser session created.')
    return browser_session
        

def get_results(session, departure_stop, arrival_stop, date, timeout):
	LOGGER.debug("Trying to find buses from {} to {} on {}".format(departure_stop, arrival_stop, date))
    
	def results_are_ready():
		results = session.driver.document().cssselect('div.search-result')
		try:
			return False if DELAY_MSG_REGEX.search(results[0].text) else True
		except:
			session.driver.render('error.png')
			LOGGER.debug("Can't get results text. You'll need to wait longer.")
    
	start_field = session.at_css('#From')
	start_field.set(departure_stop)

	destination_field = session.at_css('#To')
	destination_field.set(arrival_stop)

	departure_date = session.at_css('#When')
	current_date = datetime.date.isoformat(datetime.date.today())
	assert date >= current_date, "Can't search for bus connections in the past"
	departure_date.set(date)

	search_button = session.at_css('.btn-warning')
	search_button.click()

	waiter = WaitMixin()

	try:
		waiter.wait_for(results_are_ready, interval=0.5, timeout=timeout)
	except WaitTimeoutError as e:
		LOGGER.debug("Request timed out. See error.png for a screenshot.")
		session.driver.render('error.png')
		raise WaitTimeoutError

	results = session.driver.document().cssselect('div.search-result')
	return results, session


def parse_result(session, result):
	try:
		departure = result.xpath('div[1]/div/div[1]/div[1]')[0]
		departure_date = departure.xpath('div[1]/span[1]')[0].text
		departure_time = departure.xpath('div[1]/span[3]')[0].text
		departure_stop = departure.xpath('div[2]/span')[0].text    

		duration = result.xpath('div[1]/div/div[1]/div[2]')[0]
		trip_duration = duration.xpath('div[1]')[0].text
		number_of_stops = duration.xpath('div[2]')[0].text

		arrival = result.xpath('div[1]/div/div[1]/div[3]')[0]
		arrival_date = arrival.xpath('div[1]/span[1]')[0].text
		arrival_time = arrival.xpath('div[1]/span[3]')[0].text
		arrival_stop = arrival.xpath('div[2]/span')[0].text
		
		price_str = result.xpath('div[1]/div/div[2]/div[2]/div[1]/span[2]/strong')[0].text.split()[0]
		price = u"{0:.2f} €".format(float(COMMA_REGEX.sub('.', price_str)))
		
		company = result.xpath('div[1]/div/div[2]/div[1]/div[1]/div[1]/span[2]')[0].text
		return Connection(
			departure_date=departure_date, departure_time=departure_time,
			departure_stop=departure_stop, trip_duration=trip_duration,
			number_of_stops=number_of_stops, arrival_date=arrival_date,
			arrival_time=arrival_time, arrival_stop=arrival_stop, price=price,
			company=company)
	except:
		error_msg = "Can't parse results. See error.png/htm for details.\n{}".format(traceback.format_exc())
		LOGGER.debug(error_msg)
		session.driver.render('error.png')
		with open('error.htm', 'w') as html_file:
			html_file.write(etree.tostring(session.driver.document()))
		if DEBUG:
			pudb.set_trace()
		else:
			raise BusliniensucheParsingError(error_msg)

    
def find_bus_connections(departure_stop, arrival_stop, date, timeout):
    session = create_browser_session(url=SEARCH_PAGE)
    results, session = get_results(session, departure_stop, arrival_stop, date, timeout=timeout)
    connections = []
    for result in results:
        connections.append(parse_result(session, result))
    return connections


def results2table(connections):
    table = PrettyTable(["Departure", "Price", "From", "Arrival", "To", "Company"])
    table.align["Price"] = "r"
    table.align["From"] = "l"
    table.align["To"] = "l"
    table.align["Company"] = "l"
    for connection in connections:
        table.add_row([
            connection.departure_time, connection.price,
            connection.departure_stop[:20],
            connection.arrival_time, connection.arrival_stop[:20],
            connection.company])
    return table


def run_cli():
	parser = argparse.ArgumentParser()
	parser.add_argument('-d', '--debug', action='store_true',
	                    help='debug mode')
	parser.add_argument('-t', '--timeout', type=int, default=60,
	                    help='wait at least n seconds for results')
	parser.add_argument('origin')
	parser.add_argument('destination')
	parser.add_argument('date')
	args = parser.parse_args(sys.argv[1:])
	
	if args.debug is True:
		DEBUG = True
	
	connections = find_bus_connections(args.origin, args.destination,
									   args.date, args.timeout)
	table = results2table(connections)
	table.sort_key = natural_sort_key
	#~ # table.sortby = u"Price"
	print table


if __name__ == '__main__':
	run_cli()
