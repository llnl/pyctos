# Copyright 2025-2026 Lawrence Livermore National Security, LLC and other Pyctos Developers.
# See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

class Stack(object):
  """ A stack is an abstract data type that serves as a collection of
  elements with two principal operations: push() and pop(). push() adds an
  element to the top of the stack, and pop() removes an element from the top
  of a stack. The order in which elements come off of a stack are
  Last In, First Out (LIFO).

  https://en.wikipedia.org/wiki/Stack_(abstract_data_type)
  """

  def __init__(self, limit=10):
    self.stack = []
    self.limit = limit

  def __bool__(self):
    return bool(self.stack)

  def __str__(self):
    return str(self.stack)

  def push(self, data):
    """ Push an element to the top of the stack."""
    if len(self.stack) >= self.limit:
      raise StackOverflowError
    self.stack.append(data)

  def pop(self):
    """ Pop an element off of the top of the stack."""
    if self.stack:
      return self.stack.pop()
    else:
      raise IndexError('pop from an empty stack')

  def peek(self):
    """ Peek at the top-most element of the stack."""
    if self.stack:
      return self.stack[-1]

  def is_empty(self):
    """ Check if a stack is empty."""
    return not bool(self.stack)

  def size(self):
    """ Return the size of the stack."""
    return len(self.stack)


class StackOverflowError(BaseException):
  pass
