# Some custom commands for debugging c++ with slightly reduced despair.
#
# Assumptions: gdb 7.2, Linux, g++, 1 inferior *only*

import re

eg = "std::_Rb_tree<Tcl_Interp*, std::pair<Tcl_Interp* const, std::map<std::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::shared_ptr<Tcl::details::callback_base>, std::less<std::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::allocator<std::pair<std::basic_string<char, std::char_traits<char>, std::allocator<char> > const, std::shared_ptr<Tcl::details::callback_base> > > > >, std::_Select1st<std::pair<Tcl_Interp* const, std::map<std::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::shared_ptr<Tcl::details::callback_base>, std::less<std::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::allocator<std::pair<std::basic_string<char, std::char_traits<char>, std::allocator<char> > const, std::shared_ptr<Tcl::details::callback_base> > > > > >, std::less<Tcl_Interp*>, std::allocator<std::pair<Tcl_Interp* const, std::map<std::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::shared_ptr<Tcl::details::callback_base>, std::less<std::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::allocator<std::pair<std::basic_string<char, std::char_traits<char>, std::allocator<char> > const, std::shared_ptr<Tcl::details::callback_base> > > > > > >::_M_destroy_node"
eg2 = "std::_Rb_tree<Tcl_Interp*, std::pair<Tcl_Interp* const, std::map<std::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::shared_ptr<Tcl::details::callback_base>, std::less<std::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::allocator<std::pair<std::basic_string<char, std::char_traits<char>, std::allocator<char> > const, std::shared_ptr<Tcl::details::callback_base> > > > >, std::_Select1st<std::pair<Tcl_Interp* const, std::map<std::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::shared_ptr<Tcl::details::callback_base>, std::less<std::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::allocator<std::pair<std::basic_string<char, std::char_traits<char>, std::allocator<char> > const, std::shared_ptr<Tcl::details::callback_base> > > > > >, std::less<Tcl_Interp*>, std::allocator<std::pair<Tcl_Interp* const, std::map<std::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::shared_ptr<Tcl::details::callback_base>, std::less<std::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::allocator<std::pair<std::basic_string<char, std::char_traits<char>, std::allocator<char> > const, std::shared_ptr<Tcl::details::callback_base> > > > > > >"

def template_name_and_args(pieces):
    
    assert len(pieces) > 1
    name, first_arg = pieces[0].split('<', 1)
    last_arg, _ = pieces[-1].rsplit('>', 1)
    return name, [first_arg] + pieces[1:-1] + [last_arg.rstrip()]

def unbalanced_chevrons(lst):
    counts = map(lambda s: s.count('<') - s.count('>'), lst)
    return sum(counts) != 0

def decompose_template(comma_list, depth=0):
    assert len(comma_list) > 0
    
    if len(comma_list) == 1:
        return comma_list[0]

    decomposed_args = []
    while comma_list:
        arg = [comma_list.pop(0)]
        while unbalanced_chevrons(arg):
            assert comma_list            
            arg.append(comma_list.pop(0))
        if len(arg) > 1:
            name, inner_args = template_name_and_args(arg)
            inner_decomposed_args = decompose_template(inner_args, depth + 1)
            if name == 'std::basic_string' and \
               inner_decomposed_args == ['char', 'std::char_traits<char>', 'std::allocator<char>']:
                decomposed_args.append('std::string')
            elif name == 'std::map':
                reconstituted = name + '<' + ', '.join(inner_decomposed_args[0:2]) + ' >'
                decomposed_args.append(reconstituted)
            else:
                reconstituted = name + '<' + ', '.join(inner_decomposed_args) + ' >'
                decomposed_args.append(reconstituted)
        else:
            decomposed_args.append(arg[0])
    return decomposed_args

def simplify_template_call(name):
    m = re.match(r'([^<]+)<(.*)>::(.*)$', name)
    if not m:
        return []
    tname, fname = m.group(1), m.group(3)
    if m.group(2).count('<') == 0:
        # Simple template definition.
        return [tname, m.group(2), fname]

    # Parse nested template definition.
    targ_pieces = m.group(2).split(', ')
    return [tname, ', '.join(decompose_template(targ_pieces)),fname]

def simplify_stl_names(decl):    
    """Take common STL/Standard Library names and simplify them to help make the
    stack trace look more readable and less like the graphics in the matrix.

    """
    p = simplify_template_call(decl)
    if p == []:
        return decl
    return p[0]  + '<' + ', '.join(p[1:-1]) + '>::' + p[-1]

def simplified_back_trace():
    """Returns a simplified backtrace as a list of tuples containing frame number and
function name.

    """
    frames = []
    f = gdb.selected_frame()
    while f != None:
        frames.append(simplify_stl_names(f.name()))
        f = f.older()
    # Frame order is newest -> oldestc,
    return zip(range(len(frames)), frames)

def thread_list():
    """Return current threads sorted by LWPID."""

    # Assume there is only one inferior.
    thrs = gdb.inferiors()[0].threads()
    # Linux specific: sort by light weight pid.
    return sorted(thrs, key=lambda t: t.ptid[1])

def find_thread(thread_num):
    # Assume there is only one inferior.
    thrs = gdb.inferiors()[0].threads()
    for t in thrs:
        if t.num == thread_num:
            return t
    return None

class HelloWorld (gdb.Command):
    """Hello world!"""

    def __init__ (self):
        super (HelloWorld, self).__init__ ("hello-world", gdb.COMMAND_RUNNING)

    def invoke (self, arg, from_tty):
        print "Hello World!"

HelloWorld ()

class SbtCommand (gdb.Command):
    """Simple backtrace"""

    def __init__ (self):
        super (SbtCommand, self).__init__("sbt", gdb.COMMAND_RUNNING)

    def invoke (self, arg, from_tty):
        bt = simplified_back_trace()
        bt.reverse()            # List the inner most (newer) frames last.
        for (n, f) in bt:
            print "%4d  %s" % (n, f)

SbtCommand ()

class LtCommand (gdb.Command):
    """List threads"""

    def __init__ (self):
        super (LtCommand, self).__init__("lt", gdb.COMMAND_RUNNING)

    def invoke (self, arg, from_tty):
        # Banner
        print "%4s  %8s  %8s  %8s  %-8s  %-8s" % ("num", "pid", "lwpid", "tid", "state", "func")

        curr_thread = gdb.selected_thread()
        for t in thread_list():
            pid, lwpid, tid = t.ptid
            state = "running"
            if t.is_stopped: state = "stopped"
            elif t.is_exited: state = "exited"
            t.switch()
            func = gdb.selected_frame().name()
            print "%4d  %8d  %8d  %8d  %8s  %s" % (t.num, pid, lwpid, tid, state, func)

LtCommand ()

class ExamineThreadCommand (gdb.Command):
    """Examine thread."""

    def __init__(self):
        super (ExamineThreadCommand, self).__init__("xthread", gdb.COMMAND_RUNNING)

    def invoke(self, arg, from_tty):
        if not arg:
            print self.__doc__
            return

        curr_thread = gdb.selected_thread()
        assert curr_thread != None
        try:
            t = find_thread(int(arg))
            if not t:
                print "No such thread number:", arg
            else:
                t.switch()
                pid, lwpid, tid = t.ptid
                print "num=%d  pid=%d  lwpid=%d  tid=%d" % (t.num, pid, lwpid, tid)
                bt = simplified_back_trace()
                bt.reverse()    # List the inner most (newer) frames last.
                for (n, f) in bt:
                    print "%4d  %s" % (n, f)

        finally:
            curr_thread.switch()

ExamineThreadCommand ()
