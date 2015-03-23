from __future__ import print_function
import willie

import requests
import json
import shelve
import time
import traceback
from datetime import datetime

from ffda_lib import pretty_date, day_changed

minimum_aggregation_interval = 300
update_interval = 15
new_highscore = False
hs = None
gateways, nodes, clients = 0, 0, 0
msg = ""

def setup(bot):
    global hs, minimum_aggregation_interval, update_interval
    minimum_aggregation_interval = request.get(bot.config.freifunk.minimum_aggregation_interval)
    update_interval = request.get(bot.config.freifunk.update_interval)
    hs = shelve.open("ffda-highscore.shelve", writeback=True)

    # total highscore
    if 'nodes' not in hs:
        hs['nodes'] = 0
        hs['nodes_dt'] = time.time()
    if 'clients' not in hs:
        hs['clients'] = 0
        hs['clients_dt'] = time.time()
        hs['clients_dc'] = 0

    # end of day highscore, also clean up if we load a daychange from file
    if 'daily_dt' not in hs or day_changed(hs['daily_dt']):
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


@willie.module.interval(update_interval)
def update(bot):
    global hs, gateways, nodes, clients, new_highscore, msg, update_interval, minimum_aggregation_interval
    minimum_aggregation_interval = request.get(bot.config.freifunk.minimum_aggregation_interval)
    update_interval = request.get(bot.config.freifunk.update_interval)
    result = requests.get(bot.config.freifunk.ffmap_nodes_uri)
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
        hs['clients_dc'] = clients - hs['clients']
        hs['clients'] = clients
        hs['clients_dt'] = time.time()
        new_highscore = True
    if clients > hs['daily_clients']:
        hs['daily_clients'] = clients
        hs['daily_clients_dt'] = time.time()

    if new_highscore:
        msg = "Neuer Highscore von {} Nodes ({}) und {} (+{}) Clients ({}).".format(
                  hs['nodes'], pretty_date(hs['nodes_dt']),
                  hs['clients'], hs['clients_dc'], pretty_date(hs['clients_dt']))

    # detect daychange
    if day_changed(hs['daily_dt']):
        tpl = "Der gestrige Highscore liegt bei {} Nodes ({}) und {} Clients ({})."
        msg = tpl.format(hs['daily_nodes'], pretty_date(hs['daily_nodes_dt']),
                         hs['daily_clients'], pretty_date(hs['daily_clients_dt']))
        print(msg)
        bot.msg(bot.config.freifunk.announce_target, msg)

        # reset daily counters
        hs['daily_nodes'] = 0
        hs['daily_nodes_dt'] = time.time()
        hs['daily_clients'] = 0
        hs['daily_clients_dt'] = time.time()
        hs['daily_dt'] = time.time()

@willie.module.interval(minimum_aggregation_interval)
def announce(bot):
    global msg, new_highscore, minimum_aggregation_interval
    minimum_aggregation_interval = requests.get(bot.config.freifunk.minimum_aggregation_interval)
    if new_highscore:
        print(msg)
        bot.msg(bot.config.freifunk.announce_target, msg)
        new_highscore = False

@willie.module.commands('status')
def status(bot, trigger):
    global nodes, gateways, clients

    tpl = "Derzeit sind {} Gateways, {} Nodes (^{}) und {} Clients (^{}) online."
    msg = tpl.format(gateways, nodes, hs['daily_nodes'], clients, hs['daily_clients'])
    bot.say(msg)
    print(msg)


@willie.module.commands('highscore')
def highscore(bot, trigger):
    global hs

    tpl = "Der Highscore liegt bei {} Nodes ({}) und {} Clients ({})."
    msg = tpl.format(hs['nodes'], pretty_date(hs['nodes_dt']),
                     hs['clients'], pretty_date(hs['clients_dt']))
    bot.say(msg)
    print(msg)
