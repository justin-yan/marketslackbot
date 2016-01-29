import operator
from collections import defaultdict
import time
from slackclient import SlackClient
import configparser
from os.path import expanduser
import json
import pprint


class Market(object):

    def __init__(self, description: str):
        self.description = description
        self.bids = BidOrderChain()
        self.asks = AskOrderChain()
        self.position_book = defaultdict(Position)
        self.last_trade_price = None

    def __str__(self):
        output_string = "Market Description: {0}\n".format(self.description)
        output_string += "Bids: " + str(self.bids) + "\n"
        output_string += "Asks: " + str(self.asks) + "\n"
        output_string += "Position Book: " + str(self.position_book)
        return output_string

    def transact(self, price, quantity, buyer, seller):
        self.position_book[buyer].cash -= price * quantity
        self.position_book[buyer].net_position += quantity
        self.position_book[seller].cash += price * quantity
        self.position_book[seller].net_position -= quantity
        self.last_trade_price = price

    def bid(self, price, quantity, owner):
        cur_ask = self.asks.peek_lead()
        while cur_ask and cur_ask.price < price:  # checks for ask, then checks to see ask is cheap
            trade_qty = min(quantity, cur_ask.quantity)
            self.transact(cur_ask.price, trade_qty, owner, cur_ask.owner)
            quantity -= trade_qty
            cur_ask.quantity -= trade_qty
            if cur_ask.quantity == 0 and quantity == 0:
                self.asks.pop_lead()  # Wiped out the lowest ask
                return                # Wiped out the bid
            elif cur_ask.quantity == 0:
                self.asks.pop_lead()  # Wiped out lowest ask but not bid
            elif quantity == 0:
                return                # Wiped out bid but not lowest ask

            cur_ask = self.asks.peek_lead()

        # If you make it out of the loop without returning, the remaining quantity is ready to be inserted as an order.
        self.bids.insert_order(price, quantity, owner)

    def ask(self, price, quantity, owner):
        cur_bid = self.bids.peek_lead()
        while cur_bid and cur_bid.price > price:  # checks for bid, then checks to see bid is expensive
            trade_qty = min(quantity, cur_bid.quantity)
            self.transact(cur_bid.price, trade_qty, cur_bid.owner, owner)
            quantity -= trade_qty
            cur_bid.quantity -= trade_qty
            if cur_bid.quantity == 0 and quantity == 0:
                self.bids.pop_lead()  # Wiped out the lowest bid
                return                # Wiped out the ask
            elif cur_bid.quantity == 0:
                self.bids.pop_lead()  # Wiped out lowest bid but not ask
            elif quantity == 0:
                return                # Wiped out ask but not lowest bid

            cur_bid = self.bids.peek_lead()

        # If you make it out of the loop without returning, the remaining quantity is ready to be inserted as an order.
        self.asks.insert_order(price, quantity, owner)

    def hit(self, quantity, owner):
        while quantity > 0:
            cur_bid = self.bids.peek_lead()
            if cur_bid is None: # hit everything on the market
                break
            trade_qty = min(quantity, cur_bid.quantity)
            self.transact(cur_bid.price, trade_qty, cur_bid.owner, owner)
            quantity -= trade_qty
            cur_bid.quantity -= trade_qty

            if cur_bid.quantity == 0:
                self.bids.pop_lead()

    def lift(self, quantity, owner):
        while quantity > 0:
            cur_ask = self.asks.peek_lead()
            if cur_ask is None: # lifted everything on the market
                break
            trade_qty = min(quantity, cur_ask.quantity)
            self.transact(cur_ask.price, trade_qty, owner, cur_ask.owner)
            quantity -= trade_qty
            cur_ask.quantity -= trade_qty

            if cur_ask.quantity == 0:
                self.asks.pop_lead()

    def view_orders(self, owner=None):
        bids = []
        asks = []
        for chain, output in [(self.bids, bids), (self.asks, asks)]:
            cur_order = chain.lead
            while cur_order is not None:
                if owner is None or cur_order.owner == owner:
                    output.append(cur_order)
                cur_order = cur_order.next
        # Return the bids from highest -> lowest, asks lowest -> highest
        return {"bids":sorted(bids, key=lambda x: -x.price), "asks":sorted(asks, key=lambda x: x.price)}

    def view_positions(self, owner=None):
        if owner:
            return {owner: self.position_book[owner]}
        else:
            return self.position_book

    def clear(self, owner=None):
        if owner is None:
            self.bids = BidOrderChain()
            self.asks = AskOrderChain()
        else:
            for chain in [self.bids, self.asks]:
                prev_order = None
                cur_order = chain.lead
                while cur_order is not None:
                    if cur_order.owner == owner:
                        if prev_order:
                            prev_order.next = cur_order.next
                        else:
                            chain.lead = cur_order.next
                    else:
                        prev_order = cur_order
                    cur_order = cur_order.next

    def settle(self, price):
        cash_settlement = {}
        for k, v in self.position_book.items():
            cash_settlement[k] = v.cash + v.net_position*price
        return cash_settlement


class OrderChain(object):
    op_func = operator.ge            # default to bid
    lead_comp_func = operator.gt

    def __init__(self):
        self.lead = None

    def __str__(self):
        if self.lead is None:
            return "EmptyOrderChain"
        else:
            output_string = ""
            cur_node = self.lead
            while cur_node.next is not None:
                output_string += str(cur_node) + '->'
                cur_node = cur_node.next
            output_string += str(cur_node)
            return output_string

    def insert_order(self, price, quantity, owner):
        new_order = Order(price, quantity, owner)
        if self.lead is None:
            self.lead = new_order
        else:
            if self.lead_comp_func(new_order.price, self.lead.price):
                new_order.next = self.lead
                self.lead = new_order
            else:
                cur_order = self.lead
                while cur_order.next is not None and self.op_func(cur_order.next.price, new_order.price): # Works due to short-circuiting.  Prioritize orders in FIFO.
                    cur_order = cur_order.next
                # After exiting the while loop, we are positioned at the last node greater than our order
                new_order.next = cur_order.next
                cur_order.next = new_order


    def pop_lead(self):
        if self.lead:
            cur_lead = self.lead
            self.lead = cur_lead.next
            return cur_lead
        else:
            return None

    def peek_lead(self):
        if self.lead:
            return self.lead
        else:
            return None


class BidOrderChain(OrderChain):
    op_func = operator.ge
    lead_comp_func = operator.gt


class AskOrderChain(OrderChain):
    op_func = operator.le
    lead_comp_func = operator.lt


class Order(object):

    def __init__(self, price, quantity, owner):
        self.price = price
        self.quantity = quantity
        self.owner = owner
        self.next = None

    def __str__(self):
        return "(price={0}, quantity={1}, owner={2})".format(self.price, self.quantity, self.owner)

    def __repr__(self):
        return "(price={0}, quantity={1}, owner={2})".format(self.price, self.quantity, self.owner)


class Position(object):

    def __init__(self):
        self.cash = 0
        self.net_position = 0

    def __str__(self):
        return "(cash={0}, net_position={1})".format(self.cash, self.net_position)

    def __repr__(self):
        return "(cash={0}, net_position={1})".format(self.cash, self.net_position)


from functools import lru_cache
@lru_cache(1024)
def map_user(user_id):
    return json.loads(sc.api_call("users.info", user=user_id).decode('utf-8'))['user']['name']


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(expanduser('~') + '/.config/marketslackbot.cfg')
    token = config.get("default", "token")

    market_map = {}
    sc = SlackClient(token)
    user_id = json.loads(sc.api_call("auth.test").decode('utf-8'))['user_id']
    if sc.rtm_connect():
        while True:
            msg_list = sc.rtm_read()
            for msg in msg_list:
                print(msg)
                if msg.get('type') == 'message' and msg.get('subtype') is None and msg['channel'][0] in ['G', 'C'] and msg['user'] != user_id:
                    channel = msg['channel']
                    owner = map_user(msg['user'])
                    tokens = msg['text'].split(' ')
                    market = market_map.get(channel)
                    if len(tokens) == 1:
                        if tokens[0] == 'pos':
                            output = "```" + pprint.pformat(dict(market.view_positions())) + "```" if market else "No market is available!"
                        elif tokens[0] == 'mypos':
                            output = "```" + pprint.pformat(dict(market.view_positions(owner))) + "```" if market else "No market is available!"
                        elif tokens[0] == 'book':
                            output = "```" + pprint.pformat(market.view_orders()) + "```" if market else "No market is available!"
                        elif tokens[0] == 'mybook':
                            output = "```" + pprint.pformat(market.view_orders(owner)) + "```" if market else "No market is available!"
                        elif tokens[0] == 'stat':
                            if market:
                                orders = market.view_orders()
                                try:
                                    bid = orders['bids'][0]
                                except IndexError:
                                    bid = None
                                try:
                                    ask = orders['asks'][0]
                                except IndexError:
                                    ask = None
                                if bid is not None and ask is not None:
                                    output = "Market for {3}: {0} at {1}, last trade: {2}".format(bid.price, ask.price, market.last_trade_price, market.description)
                                else:
                                    output = "Market for {1}: last trade: {0}".format(market.last_trade_price, market.description)
                            else:
                                output = "No market is available!"
                        elif tokens[0] == 'clear':
                            if market:
                                market.clear(owner)
                                output = "{0}'s orders cleared!".format(owner)
                            else:
                                output = "No market is available!"
                        else: # not a valid command
                            output = False
                    elif len(tokens) == 2:
                        if tokens[0] == "<@{0}>:".format(user_id):
                            if tokens[1] == "help":
                                output = """
```
Hi! I'm here to help run a market so that you can trade!

Invite me to a slack channel first!  From there, you can interact with me through the following commands:

@marketbot help
@marketbot details
bid <price:float>
bid <price:float> for <qty:int>
ask <price:float>
ask <price:float> for <qty:int>
hit <qty:int>
lift <qty:int>

marketstart <asset:string#no_spaces>   // launch a new market in <asset>
marketsettle <price:float>  // settle current market at <price> and close the market
pos    // view entire market's positions
mypos  // view your current positions
book   // view entire market book and description
mybook // view your current orders
stat   // view the description, bid-ask spread, and last trade price of the market
clear  // removes all of your orders
```
"""
                            if tokens[1] == "details":
                                output = '''
```
A quick run through on some of the finer points of working with me:

I allow one market at a time per channel. (Sorry, I know derivatives and arbitrage would be fun)
A market is in some asset which *you* will manually settle at a final price (For example, you could trade on the probability of an event, and you would settle at 1 if it happened, 0 if it didn't).
You can short arbitrarily with no costs - all assets are synthetics that will settle to cash at the <price> set by the marketsettle command.  That will then be added (or subtracted if you're short) to your final cash position.
Bids and Asks should be treated as standing limit orders with no Fill or Kill provision (partial orders will happen).  A bid will fill any standing offers at the asking price if it's less than the bid (vice versa applies).
Because I'm lazy, if you hit or lift yourself, you'll trade with yourself - this has no net effect on your positions as they will net to 0, but will eliminate your standing trades and also decrease the quantity that you end up hitting/lifting by.
Trades resolve by best price, and then FIFO in event of ties.
```
'''
                        elif tokens[0] == 'marketstart':
                            if market:
                                output = "Market already exists!"
                            else:
                                market_map[channel] = Market(tokens[1])
                                output = "Market for {0} started!".format(tokens[1])
                        elif tokens[0] == 'marketsettle':
                            if market:
                                try:
                                    output = "```" + pprint.pformat(market.settle(float(tokens[1]))) + "```"
                                    market_map.pop(channel)
                                except ValueError:
                                    output = "Need a valid float to settle market"
                            else:
                                output = "No market is available!"
                        elif tokens[0] == 'hit':
                            if market:
                                try:
                                    market.hit(int(tokens[1]), owner)
                                    output = "{0} Hit Received".format(owner)
                                except ValueError:
                                    output = "Need valid int to hit"
                            else:
                                output = "No market is available!"
                        elif tokens[0] == 'lift':
                            if market:
                                try:
                                    market.lift(int(tokens[1]), owner)
                                    output = "{0} - Lift Received".format(owner)
                                except ValueError:
                                    output = "Need valid int to lift"
                            else:
                                output = "No market is available!"
                        elif tokens[0] == 'bid':
                            if market:
                                try:
                                    market.bid(float(tokens[1]), 1, owner)
                                    output = "{0} - Bid Received".format(owner)
                                except ValueError:
                                    output = "Need valid float for bid price"
                            else:
                                output = "No market is available!"
                        elif tokens[0] == 'ask':
                            if market:
                                try:
                                    market.ask(float(tokens[1]), 1, owner)
                                    output = "{0} - Ask Received".format(owner)
                                except ValueError:
                                    output = "Need valid float for ask price"
                            else:
                                output = "No market is available!"
                        else: # not a valid command
                            output = False
                    elif len(tokens) == 4 and tokens[2] == 'for':
                        if tokens[0] == 'bid':
                            if market:
                                try:
                                    price = float(tokens[1])
                                    try:
                                        qty = int(tokens[3])
                                        market.bid(float(price), qty, owner)
                                        output = "{0} - Bid Received".format(owner)
                                    except ValueError:
                                        output = "Need valid int for bid qty"
                                except ValueError:
                                    output = "Need valid float for bid price"
                            else:
                                output = "No market is available!"
                        elif tokens[0] == 'ask':
                            if market:
                                try:
                                    price = float(tokens[1])
                                    try:
                                        qty = int(tokens[3])
                                        market.ask(float(price), qty, owner)
                                        output = "{0} - Ask Received".format(owner)
                                    except ValueError:
                                        output = "Need valid int for ask qty"
                                except ValueError:
                                    output = "Need valid float for ask price"
                            else:
                                output = "No market is available!"
                        else: # not a valid command
                            output = False
                    else:
                        output = False

                    if output:
                        sc.rtm_send_message(msg['channel'], output)
