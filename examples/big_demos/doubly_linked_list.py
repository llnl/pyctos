# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

class LinkedList:  # making main class named linked list
  def __init__(self):
    self.head = None
    self.tail = None

  def insertHead(self, x):
    newLink = Link(x)  # Create a new link with a value attached to it
    if (self.isEmpty() == True):  # Set the first element added to be the tail
      self.tail = newLink
    else:
      self.head.previous = newLink             # newLink <-- currenthead(head)
    # newLink <--> currenthead(head)
    newLink.next = self.head
    self.head = newLink                          # newLink(head) <--> oldhead

  def deleteHead(self):
    temp = self.head
    # oldHead <--> 2ndElement(head)
    self.head = self.head.next
    # oldHead --> 2ndElement(head) nothing pointing at it so the old head will be removed
    self.head.previous = None
    if (self.head is None):
      self.tail = None  # if empty linked list
    return temp

  def insertTail(self, x):
    newLink = Link(x)
    # currentTail(tail)    newLink -->
    newLink.next = None
    # currentTail(tail) --> newLink -->
    self.tail.next = newLink
    newLink.previous = self.tail  # currentTail(tail) <--> newLink -->
    # oldTail <--> newLink(tail) -->
    self.tail = newLink

  def deleteTail(self):
    temp = self.tail
    # 2ndLast(tail) <--> oldTail --> None
    self.tail = self.tail.previous
    self.tail.next = None                       # 2ndlast(tail) --> None
    return temp

  def delete(self, x):
    current = self.head

    while (current.value != x):                  # Find the position to delete
      current = current.next

    if (current == self.head):
      self.deleteHead()

    elif (current == self.tail):
      self.deleteTail()

    else:  # Before: 1 <--> 2(current) <--> 3
      current.previous.next = current.next  # 1 --> 3
      current.next.previous = current.previous  # 1 <--> 3

  def isEmpty(self):  # Will return True if the list is empty
    return (self.head is None)


class Link:
  next = None  # This points to the link in front of the new link
  previous = None  # This points to the link behind the new link

  def __init__(self, x):
    self.value = x

  def displayLink(self):
    print("{}".format(self.value), end=" ")
