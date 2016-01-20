import operator
from collections import defaultdict
import time
from slackclient import SlackClient


class Market(object):

    def __init__(self, description: str):
        self.description = description
        self.bids = BidOrderChain()
        self.asks = AskOrderChain()
        self.position_book = defaultdict(Position)

    def __str__(self):
        output_string = "Market Description: {0}\n".format(self.description)
        output_string += "Bids: " + str(self.bids) + "\n"
        output_string += "Asks: " + str(self.asks) + "\n"
        output_string += "Position Book: " + str(self.position_book)
        return output_string

    def transact(self, price, quantity, buyer, seller):
        self.position_book[buyer].cash -= price * quantity
        self.position_book[buyer].net_long += quantity
        self.position_book[seller].cash += price * quantity
        self.position_book[seller].net_long -= quantity

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
            trade_qty = min(quantity, cur_bid.quantity)
            self.transact(cur_bid.price, trade_qty, cur_bid.owner, owner)
            quantity -= trade_qty
            cur_bid.quantity -= trade_qty

            if cur_bid.quantity == 0:
                self.bids.pop_lead()

    def lift(self, quantity):
        while quantity > 0:
            cur_ask = self.asks.peek_lead()
            trade_qty = min(quantity, cur_ask.quantity)
            self.transact(cur_bid.price, trade_qty, owner, cur_ask.owner)
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
        return [sorted(bids, key=lambda x: x.price), sorted(asks, key=lambda x: x.price)]

    def view_positions(self, owner=None):
        if owner:
            return self.position_book[owner]
        else:
            return [i for i in self.position_book.items()]

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
            cash_settlement[k] = v.cash + v.net_long*price
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
        return "(" + ",".join([str(self.price), str(self.quantity), self.owner]) + ")"

    def __repr__(self):
        return "(" + ",".join([str(self.price), str(self.quantity), self.owner]) + ")"


class Position(object):

    def __init__(self):
        self.cash = 0
        self.net_long = 0

    def __str__(self):
        return "(cash:{0}, net_long:{1})".format(self.cash, self.net_long)

    def __repr__(self):
        return "(cash:{0}, net_long:{1})".format(self.cash, self.net_long)


if __name__ == '__main__':
    pass