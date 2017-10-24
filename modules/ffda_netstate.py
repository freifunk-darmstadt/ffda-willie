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
    result.encoding = "UTF-8"
    try:
        mapdata = json.loads(result.text)
    except ValueError:
        print(traceback.format_exc())
        return

    gateway_set = set()
    nodes = 0
    clients = 0
    for node in mapdata['nodes']:
        try:
            if not node['flags']['online']:
                continue
            if 'gateway' in node['statistics']:
                gateway_set.add(node['statistics']['gateway'])
        except KeyError:
            continue

        nodes += 1
        try:
            clients += node['statistics'].get('clients', 0)
        except KeyError:
            pass

    bot.memory['ffda']['status'] = (nodes, len(gateway_set), clients)
    try:
        update_highscore(bot, nodes, len(gateway_set), clients)
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
    status = bot.memory['ffda'].get('status', None)

    if status is None:
        bot.say('Noch keine Daten.')
        return

    nodes, gateways, clients = status

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

    monday = get_next_plenum()

    url = urljoin(bot.config.freifunk.padserver, 'ffda-{year}{month}{day}'.format(
        year=monday.year, month=str(monday.month).zfill(2), day=str(monday.day).zfill(2)))

    bot.say(url)


@willie.module.commands('commands')
@willie.module.commands('help')
@willie.module.commands('rtfm')
@willie.module.commands('man')
def ffda_help(bot, trigger):
    # restrict to announce channel
    if not trigger.args[0] == bot.config.freifunk.announce_target:
        return

    prefix = bot.config.core.prefix
    commands = ( '{prefix}{cmd}'.format(prefix=prefix, cmd=cmd) for cmd in ('agenda', 'highscore', 'status'))

    msg = "Befehle: {cmds}".format(cmds=', '.join(commands))

    bot.say(msg)

@willie.module.require_admin
@willie.module.commands('set')
def ffda_set(bot, trigger):
    dt_format = '%Y-%m-%d %H:%M:%S'


    args = trigger.args[1].split(' ')[1:]
    mem = bot.memory['ffda']['highscore']

    key = args[0]

    value = ' '.join(args[1:])

    print(args, value)

    if key not in mem:
        bot.reply('Nope! valid keys: {}'.format(','.join(mem.keys())))
        return

    if key.endswith('_dt'):
        try:
            value = (datetime.strptime(value, dt_format) - datetime.fromtimestamp(0)).total_seconds()
        except ValueError:
            bot.reply("Invalid format, please use {} for _dt's".format(dt_format))
            return
        else:
            mem[key] = value
    else:
        try:
            value = int(value)
        except ValueError:
            bot.reply('Nope! Please supply int values.')
            return
        else:
            mem[key] = value

    bot.reply('set {} to {}'.format(key, value))

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
            return "vor {0:.2f} Sekunden".format(second_diff)
        if second_diff < 120:
            return "vor einer Minute"
        if second_diff < 3600:
            return "vor {0:.2f} Minuten".format(second_diff / 60)
        if second_diff < 7200:
            return "vor einer Stunde"
        if second_diff < 86400:
            return "vor {0:.2f} Stunden".format(second_diff / 3600)
    if day_diff == 1:
        return "gestern"
    if day_diff < 7:
        return "vor {0:.2f} Tagen".format(day_diff)

    return "am {0}".format(compare.strftime('%d.%m.%Y um %H:%M Uhr'))


def day_changed(since):
    then = datetime.fromtimestamp(since).strftime('%x')
    return then != time.strftime('%x')

def get_next_plenum(now=None):
    if now is None:
        now = datetime.now()

    if now.weekday() is not 0:
        next_monday = now + timedelta(days=7-now.weekday())
    else:
        next_monday = now

    next_plenum = next_monday.replace(hour=19, minute=30, second=0, microsecond=0)
    return next_plenum
