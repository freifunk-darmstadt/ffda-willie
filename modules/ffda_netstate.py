from __future__ import print_function
import willie

import requests
import json
import shelve
import time
import traceback
from datetime import datetime

from ffda_lib import pretty_date

hs = None
gateways, nodes, clients = 0, 0, 0


def setup(bot):
    global hs

    hs = shelve.open("ffda-highscore.shelve", writeback=True)

    # total highscore
    if 'nodes' not in hs:
        hs['nodes'] = 0
        hs['nodes_dt'] = time.time()
    if 'clients' not in hs:
        hs['clients'] = 0
        hs['clients_dt'] = time.time()

    # end of day highscore, also clean up if we load a daychange from file
    if 'daily' not in hs or \
       datetime.fromtimestamp(hs['daily_dt']).strftime('%x') != time.strftime('%x'):
        hs['daily_nodes'] = 0
        hs['daily_nodes_dt'] = time.time()
        hs['daily_clients'] = 0
        hs['daily_clients_dt'] = time.time()
        hs['daily_dt'] = time.time()


def shutdown(bot):
    global hs

    if hs is not None:
        hs.sync()
        hs.close()


@willie.module.interval(15)
def update(bot):
    global hs, gateways, nodes, clients

    result = requests.get('https://map.darmstadt.freifunk.net/nodes.json')
    try:
        mapdata = json.loads(result.text)
    except ValueError:
        print(traceback.format_exc())
        return

    gateways = 0
    nodes = 0
    clients = 0
    for node in mapdata['nodes']:
        try:
            if not node['flags']['online']:
                continue
            if node['flags']['gateway']:
                gateways += 1
                continue
        except KeyError:
            continue

        nodes += 1
        clients += node.get('clientcount', 0)

    # print(nodes, clients)

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
        message = "Neuer Highscore von {} Nodes ({}) und {} Clients ({}).".format(
                  hs['nodes'], pretty_date(hs['nodes_dt']),
                  hs['clients'], pretty_date(hs['clients_dt']))

        print(message)
        bot.msg(bot.config.ffda.msg_target, message)

    # detect daychange
    if datetime.fromtimestamp(hs['daily_dt']).strftime('%x') != time.strftime('%x'):
        message = "Der gestrige Highscore liegt bei {} Nodes ({}) und {} Clients ({}).".format(
            hs['daily_nodes'], pretty_date(hs['daily_nodes_dt']),
            hs['daily_clients'], pretty_date(hs['daily_clients_dt']))

        print(message)
        bot.msg(bot.config.ffda.msg_target, message)

        # reset daily counters
        hs['daily_nodes'] = 0
        hs['daily_nodes_dt'] = time.time()
        hs['daily_clients'] = 0
        hs['daily_clients_dt'] = time.time()
        hs['daily_dt'] = time.time()


@willie.module.commands('status')
def status(bot, trigger):
    global nodes, gateways, clients

    message = "Derzeit sind {} Gateways, {} Nodes (^{}) und {} Clients (^{}) online.".format(
              gateways, nodes, hs['daily_nodes'], clients, hs['daily_clients'])

    print(message)
    bot.msg(bot.config.ffda.msg_target, message)


@willie.module.commands('highscore')
def highscore(bot, trigger):
    global hs

    message = "Der Highscore liegt bei {} Nodes ({}) und {} Clients ({}).".format(
              hs['nodes'], pretty_date(hs['nodes_dt']),
              hs['clients'], pretty_date(hs['clients_dt']))

    print(message)
    bot.msg(bot.config.ffda.msg_target, message)
