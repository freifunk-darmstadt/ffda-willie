# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import shelve
import time
import traceback
from datetime import datetime, date, timedelta

import requests
from requests.compat import urljoin

import willie


def setup(bot):
    hs = shelve.open("ffda-highscore", writeback=True)

    # total highscore
    if 'nodes' not in hs:
        hs['nodes'] = 0
        hs['nodes_dt'] = time.time()
    if 'clients' not in hs:
        hs['clients'] = 0
        hs['clients_dt'] = time.time()

    # end of day highscore, also clean up if we load a daychange from file
    try:
        if day_changed(hs['daily_dt']):
            reset_highscore(hs)
    except KeyError:
        reset_highscore(hs)

    bot.memory['ffda'] = {'highscore': hs}


def reset_highscore(highscore):
    highscore['daily_nodes'] = 0
    highscore['daily_nodes_dt'] = time.time()
    highscore['daily_clients'] = 0
    highscore['daily_clients_dt'] = time.time()
    highscore['daily_dt'] = time.time()


def shutdown(bot):
    try:
        hs = bot.memory['ffda']['highscore']
        hs.close()
    except KeyError:
        pass


@willie.module.interval(15)
def update(bot):
    result = requests.get(bot.config.freifunk.ffmap_nodes_uri)
    try:
        mapdata = json.loads(result.text)
    except ValueError:
        print(traceback.format_exc())
        return

    gateways = 0
    nodes = 0
    clients = 0
    for nodeid, node in mapdata['nodes'].items():
        try:
            if not node['flags']['online']:
                continue
            if node['flags']['gateway']:
                gateways += 1
                continue
        except KeyError:
            continue

        nodes += 1
        try:
            clients += node['statistics'].get('clients', 0)
        except KeyError:
            pass

    bot.memory['ffda']['status'] = (nodes, gateways, clients)
    try:
        update_highscore(bot, nodes, gateways, clients)
    except ValueError:
        print('Warning: Unable to update highscore on closed shelve.')
        print(traceback.format_exc())


def update_highscore(bot, nodes, gateways, clients):
    hs = bot.memory['ffda']['highscore']

    # total highscore
    new_highscore = False
    if nodes > hs['nodes']:
        hs['nodes'] = nodes
        hs['nodes_dt'] = time.time()
        new_highscore = True
    if nodes > hs['daily_nodes']:
        hs['daily_nodes'] = nodes
        hs['daily_nodes_dt'] = time.time()

    if clients > hs['clients']:
        hs['clients'] = clients
        hs['clients_dt'] = time.time()
        new_highscore = True
    if clients > hs['daily_clients']:
        hs['daily_clients'] = clients
        hs['daily_clients_dt'] = time.time()

    if new_highscore:
        msg = "Neuer Highscore von {} Nodes ({}) und {} Clients ({}).".format(
                  hs['nodes'], pretty_date(hs['nodes_dt']),
                  hs['clients'], pretty_date(hs['clients_dt']))
        print(msg)
        bot.msg(bot.config.freifunk.announce_target, msg)

    # detect daychange
    if day_changed(hs['daily_dt']):
        tpl = "Der gestrige Highscore liegt bei {} Nodes ({}) und {} Clients ({})."
        msg = tpl.format(hs['daily_nodes'], pretty_date(hs['daily_nodes_dt']),
                         hs['daily_clients'], pretty_date(hs['daily_clients_dt']))
        print(msg)
        bot.msg(bot.config.freifunk.announce_target, msg)

        reset_highscore(hs)

    bot.memory['ffda']['highscore'] = hs


@willie.module.commands('status')
def status(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    hs = bot.memory['ffda']['highscore']
    nodes, gateways, clients = bot.memory['ffda']['status']

    tpl = "Derzeit sind {} Gateways, {} Nodes (^{}) und {} Clients (^{}) online."
    msg = tpl.format(gateways, nodes, hs['daily_nodes'], clients, hs['daily_clients'])
    bot.say(msg)
    print(msg)


@willie.module.commands('highscore')
def highscore(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    hs = bot.memory['ffda']['highscore']

    tpl = "Der Highscore liegt bei {} Nodes ({}) und {} Clients ({})."
    msg = tpl.format(hs['nodes'], pretty_date(hs['nodes_dt']),
                     hs['clients'], pretty_date(hs['clients_dt']))
    bot.say(msg)
    print(msg)


@willie.module.commands('agenda')
def agenda(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    today = date.today()
    if today.weekday() == 0:
        monday = today
    else:
        monday = today + timedelta(days=-today.weekday(), weeks=1)

    url = urljoin(bot.config.freifunk.padserver, 'ffda-{y}{m}{d}'.format(y=monday.year, m=monday.month, d=monday.day))

    bot.say(url)


def pretty_date(timestamp=None):
    """
    Get a datetime object or a int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc
    """
    now = datetime.now()
    compare = None
    if isinstance(timestamp, int):
        compare = datetime.fromtimestamp(timestamp)
    elif isinstance(timestamp, float):
        compare = datetime.fromtimestamp(int(timestamp))
    elif isinstance(timestamp, datetime):
        compare = timestamp
    elif not timestamp:
        compare = now

    diff = now - compare
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "gerade eben"
        if second_diff < 60:
            return "vor {0} Sekunden".format(second_diff)
        if second_diff < 120:
            return "vor einer Minute"
        if second_diff < 3600:
            return "vor {0} Minuten".format(second_diff / 60)
        if second_diff < 7200:
            return "vor einer Stunde"
        if second_diff < 86400:
            return "vor {0:.2f} Stunden".format(second_diff / 3600)
    if day_diff == 1:
        return "gestern"
    if day_diff < 7:
        return "vor {0} Tagen".format(day_diff)

    return "am {0}".format(compare.strftime('%d.%m.%Y um %H:%M Uhr'))


def day_changed(since):
    then = datetime.fromtimestamp(since).strftime('%x')
    return then != time.strftime('%x')
