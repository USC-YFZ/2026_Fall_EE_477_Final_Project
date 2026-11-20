#!/usr/bin/env python3
"""EE 477L final project: test-vector generator (8-bit ALU with FSM controller).

Usage:  python3 make_vectors.py [VDD]        (default VDD = 1.0)

Creates one folder per test.  Each folder holds
  <test>.vec     Cadence digital vector file with ALL inputs of the test (one column per input bit)
  expected.csv   strobe times and expected output values
Time unit in the .vec files is ns (tunit), logic 1 = vih = VDD volts.
Opcodes: ADD=001 SUB=010 AND=011 OR=100 XOR=101 SHL=110 (logical shift left by B[2:0])
"""
import os, sys, csv

VDD = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
RISE = 0.1  # ns, edge time
OPC = {'ADD': 1, 'SUB': 2, 'AND': 3, 'OR': 4, 'XOR': 5, 'SHL': 6}
STATES = ['IDLE', 'ADD', 'SUB', 'AND', 'OR', 'XOR', 'SHL', 'DONE']   # state code = index


# ------------------------------------------------------------ reference (plain arithmetic)
def addsub(A, B, sub):
    Bx = (B ^ 0xFF) if sub else B
    t = A + Bx + sub
    s = t & 0xFF
    c8 = (t >> 8) & 1
    c7 = (((A & 0x7F) + (Bx & 0x7F) + sub) >> 7) & 1
    return s, c7, c8


def logic(A, B, fn):
    return (A & B, A | B, A ^ B)[fn]


def flags(res, arith, c7, c8):
    return int(res == 0), (res >> 7) & 1, c8 & arith, (c7 ^ c8) & arith


def state_outputs(name):
    """sub arith grp fn ld_res done for a state"""
    t = {'IDLE': (0, 0, 0, 0, 0, 0), 'ADD': (0, 1, 0, 0, 1, 0), 'SUB': (1, 1, 0, 0, 1, 0),
         'AND': (0, 0, 1, 0, 1, 0), 'OR': (0, 0, 1, 1, 1, 0), 'XOR': (0, 0, 1, 2, 1, 0),
         'SHL': (0, 0, 2, 0, 1, 0), 'DONE': (0, 0, 0, 0, 0, 1)}
    return t[name]


def fsm_next_eq(idle, done, start, op):
    E = int(not (idle or done))
    DS = done & start
    V = int(not (op == 7))
    G = idle & start & V
    X = E | DS
    return sum((((G & ((op >> i) & 1)) | X) << i) for i in range(3))


# ------------------------------------------------------------ .vec writer
def fmt_t(t):
    return ('%.2f' % t).rstrip('0').rstrip('.')


def write_vec(folder, name, signals, tend):
    """One .vec file (Cadence digital vector file): a row for every time at which some input changes."""
    names = list(signals)
    ev = {n: sorted(signals[n], key=lambda e: e[0]) for n in names}
    times = sorted({0.0, tend} | {t for n in names for t, _ in ev[n]})

    def val(n, t):
        v = ev[n][0][1]
        for tt, vv in ev[n]:
            if tt <= t:
                v = vv
        return v

    w = max(len(n) for n in names)
    with open(os.path.join(folder, name + '.vec'), 'w') as f:
        f.write('radix ' + ' '.join(['1'] * len(names)) + '\n')
        f.write('io    ' + ' '.join(['i'] * len(names)) + '\n')
        f.write('vname ' + ' '.join(names) + '\n\n')
        f.write('; --- Timing information ---\n')
        f.write('tunit 1ns\ntrise 0.01\ntfall 0.01\n')
        f.write('vih   %.1f\nvil   0.0\n\n' % VDD)
        f.write('; time(ns)  ' + ' '.join(names) + '\n')
        for t in times:
            f.write('%-8s ' % fmt_t(t) + ' '.join(str(val(n, t)).ljust(len(n)) for n in names).rstrip() + '\n')


def bits(prefix, width, series, slot, t0=0.0):
    return {'%s%d' % (prefix, b): [(t0 + k * slot, (v >> b) & 1) for k, v in enumerate(series)] for b in range(width)}


def scalar(name, series, slot, t0=0.0):
    return {name: [(t0 + k * slot, v) for k, v in enumerate(series)]}


def clock_events(tend):
    ev = [(0.0, 0)]
    t = 5.0
    while t < tend:
        ev += [(t, 1), (t + 5.0, 0)]
        t += 10.0
    return {'clk': ev}


def emit(test, signals, rows, header, tend):
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), test)
    os.makedirs(folder, exist_ok=True)
    write_vec(folder, test, signals, tend)
    with open(os.path.join(folder, 'expected.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


H = lambda v, n=2: format(v, '0%dX' % n)
TESTS = {}
SL = 10.0   # slot for combinational tests


def t1():   # rca8
    vec = [(0, 0, 0), (0xFF, 1, 0), (0x7F, 1, 0), (0x80, 0x80, 0), (0x0F, 1, 0), (0x12, 0x34, 0), (5, 3, 1), (3, 5, 1),
           (0x80, 1, 1), (0x55, 0x55, 1), (0, 1, 1), (0x7F, 0xFF, 1), (0xAA, 0x55, 0), (0xF0, 0x0F, 1)]
    sig = {}
    sig.update(bits('A', 8, [v[0] for v in vec], SL))
    sig.update(bits('B', 8, [v[1] for v in vec], SL))
    sig.update(scalar('sub', [v[2] for v in vec], SL))
    rows = []
    for k, (A, B, sub) in enumerate(vec):
        s, c7, c8 = addsub(A, B, sub)
        rows.append([k * SL + 9, H(A), H(B), sub, H(s), c8, c7, c7 ^ c8])
    hdr = ['strobe_ns', 'A', 'B', 'sub', 'S[7:0]', 'c8 (C)', 'c7', 'V']
    emit('t1_rca8', sig, rows, hdr, len(vec) * SL)
    TESTS['t1'] = (hdr, rows, len(vec) * SL)


def t2():   # logic8
    vec = [(0xAA, 0x55, 0), (0xAA, 0x55, 1), (0xAA, 0x55, 2), (0xF0, 0x3C, 0), (0xF0, 0x3C, 1), (0xF0, 0x3C, 2),
           (0xFF, 0xFF, 0), (0xFF, 0xFF, 2), (0, 0, 1)]
    sig = {}
    sig.update(bits('A', 8, [v[0] for v in vec], SL))
    sig.update(bits('B', 8, [v[1] for v in vec], SL))
    sig.update(bits('fn', 2, [v[2] for v in vec], SL))
    rows = [[k * SL + 9, H(A), H(B), format(fn, '02b'), H(logic(A, B, fn))] for k, (A, B, fn) in enumerate(vec)]
    hdr = ['strobe_ns', 'A', 'B', 'fn[1:0]', 'y[7:0]']
    emit('t2_logic8', sig, rows, hdr, len(vec) * SL)
    TESTS['t2'] = (hdr, rows, len(vec) * SL)


def shl(A, n):
    return (A << (n & 7)) & 0xFF


def t3():   # shift8: logical shift left by sh[2:0]
    vec = [(0x01, 0), (0x01, 7), (0xFF, 1), (0xFF, 4), (0xA5, 3), (0x81, 1), (0x3C, 2), (0x55, 5), (0xFF, 7), (0x80, 1),
           (0x12, 0), (0x0F, 4)]
    sig = {}
    sig.update(bits('A', 8, [v[0] for v in vec], SL))
    sig.update(bits('sh', 3, [v[1] for v in vec], SL))
    rows = [[k * SL + 9, H(A), format(n, '03b'), H(shl(A, n))] for k, (A, n) in enumerate(vec)]
    hdr = ['strobe_ns', 'A', 'sh[2:0]', 'y[7:0]']
    emit('t3_shift8', sig, rows, hdr, len(vec) * SL)
    TESTS['t3'] = (hdr, rows, len(vec) * SL)


def t4():   # result stage (clocked)
    # (add, logic, mul, grp, ld, c7, c8, arith)
    vec = [(0, 0, 0, 0, 0, 0, 0, 0),
           (0x3A, 0xC5, 0xE1, 0, 1, 0, 0, 1),
           (0x3A, 0xC5, 0xE1, 1, 1, 0, 0, 0),
           (0x3A, 0xC5, 0xE1, 2, 1, 0, 0, 0),
           (0x11, 0x22, 0x44, 1, 0, 1, 1, 1),
           (0x00, 0x22, 0x44, 0, 1, 0, 0, 1),
           (0xFF, 0x22, 0x44, 0, 1, 0, 1, 1),
           (0x80, 0x22, 0x44, 0, 1, 1, 1, 1),
           (0x7F, 0x22, 0x44, 0, 1, 1, 1, 0),
           (0x7F, 0x22, 0x0C, 2, 1, 0, 0, 0)]
    tend = len(vec) * SL
    sig = {}
    for i, nm in enumerate(('add_i', 'logic_i', 'shift_i')):
        sig.update(bits(nm + '_', 8, [v[i] for v in vec], SL))
    sig.update(bits('grp', 2, [v[3] for v in vec], SL))
    sig.update(scalar('ld_res', [v[4] for v in vec], SL))
    sig.update(scalar('c7', [v[5] for v in vec], SL))
    sig.update(scalar('c8', [v[6] for v in vec], SL))
    sig.update(scalar('arith', [v[7] for v in vec], SL))
    sig.update(clock_events(tend))
    sig['rst'] = [(0.0, 1), (8.0, 0)]
    rows = []
    res, fl = 0, (0, 0, 0, 0)
    for k, v in enumerate(vec):
        if k > 0 and v[4]:
            res = v[v[3]]
            fl = flags(res, v[7], v[5], v[6])
        rows.append([k * SL + 9, H(v[0]), H(v[1]), H(v[2]), v[3], v[4], v[5], v[6], v[7], H(res), *fl])
    hdr = ['strobe_ns', 'add_i', 'logic_i', 'mul_i', 'grp', 'ld_res', 'c7', 'c8', 'arith', 'result', 'Z', 'N', 'C', 'V']
    emit('t4_result_stage', sig, rows, hdr, tend)
    TESTS['t4'] = (hdr, rows, tend)


def t5():   # state decoder
    sig = {}
    sig.update(bits('s', 3, list(range(8)), SL))
    rows = [[k * SL + 9, format(k, '03b'), 'S_' + STATES[k]] for k in range(8)]
    hdr = ['strobe_ns', 's[2:0]', 'the one output that is 1']
    emit('t5_fsm_dec', sig, rows, hdr, 8 * SL)
    TESTS['t5'] = (hdr, rows, 8 * SL)


def t6():   # next-state logic
    vec = [(1, 0, 0, 1), (1, 0, 0, 6), (1, 0, 1, 1), (1, 0, 1, 2), (1, 0, 1, 3), (1, 0, 1, 4), (1, 0, 1, 5), (1, 0, 1, 6),
           (1, 0, 1, 0), (1, 0, 1, 7), (0, 0, 0, 5), (0, 0, 1, 1), (0, 0, 1, 6), (0, 1, 1, 0), (0, 1, 0, 3), (0, 1, 1, 5)]
    sig = {}
    sig.update(scalar('S_IDLE', [v[0] for v in vec], SL))
    sig.update(scalar('S_DONE', [v[1] for v in vec], SL))
    sig.update(scalar('start', [v[2] for v in vec], SL))
    sig.update(bits('op', 3, [v[3] for v in vec], SL))
    rows = []
    for k, (i, d, s, op) in enumerate(vec):
        rows.append([k * SL + 9, i, d, s, format(op, '03b'), format(fsm_next_eq(i, d, s, op), '03b')])
    hdr = ['strobe_ns', 'S_IDLE', 'S_DONE', 'start', 'op[2:0]', 'NS[2:0]']
    emit('t6_fsm_next', sig, rows, hdr, len(vec) * SL)
    TESTS['t6'] = (hdr, rows, len(vec) * SL)


def t7():   # output logic: one-hot state lines
    sig = {}
    for j, nm in enumerate(STATES):
        sig['S_' + nm] = [(k * SL, int(k == j)) for k in range(8)]
    rows = []
    for k, nm in enumerate(STATES):
        o = state_outputs(nm)
        rows.append([k * SL + 9, 'S_' + nm, o[0], o[1], format(o[2], '02b'), format(o[3], '02b'), o[4], o[5]])
    hdr = ['strobe_ns', 'active line', 'sub', 'arith', 'grp[1:0]', 'fn[1:0]', 'ld_res', 'done']
    emit('t7_fsm_out', sig, rows, hdr, 8 * SL)
    TESTS['t7'] = (hdr, rows, 8 * SL)


def t8():   # fsm_ctrl, 60 ns slots
    S = 60.0
    nslot = 11
    tend = nslot * S
    start_ev = [(0.0, 0)]
    op_ev = [(0.0, 0)]
    rst_ev = [(0.0, 1), (30.0, 0)]
    names = ['ADD', 'SUB', 'AND', 'OR', 'XOR', 'SHL']
    for k, nm in enumerate(names):
        t = S * (k + 1)
        start_ev += [(t, 1), (t + 10.0, 0)]
        op_ev += [(t, OPC[nm])]
    t = S * 7                      # held start, op = OR
    start_ev += [(t, 1), (t + 40.0, 0)]
    op_ev += [(t, OPC['OR'])]
    t = S * 8                      # reset in the middle of an ADD
    start_ev += [(t, 1), (t + 10.0, 0)]
    op_ev += [(t, OPC['ADD'])]
    rst_ev += [(t + 12.0, 1), (t + 20.0, 0)]
    t = S * 9                      # op = 000 with start
    start_ev += [(t, 1), (t + 10.0, 0)]
    op_ev += [(t, 0)]
    t = S * 10                     # op = 111 with start
    start_ev += [(t, 1), (t + 10.0, 0)]
    op_ev += [(t, 7)]
    sig = {'start': start_ev, 'rst': rst_ev}
    for b in range(3):
        sig['op%d' % b] = [(t, (v >> b) & 1) for t, v in op_ev]
    sig.update(clock_events(tend))
    rows = []

    def row(t, case, st):
        o = state_outputs(st)
        rows.append([t, case, format(STATES.index(st), '03b'), o[0], o[1], format(o[2], '02b'), format(o[3], '02b'), o[4], o[5]])

    for k, nm in enumerate(names):
        b = S * (k + 1)
        row(b + 14, nm + ' exec', nm)
        row(b + 24, nm + ' done', 'DONE')
        row(b + 34, nm + ' back', 'IDLE')
    b = S * 7
    row(b + 14, 'held start: exec', 'OR')
    for dt in (24, 34, 44):
        row(b + dt, 'held start: wait', 'DONE')
    row(b + 54, 'held start: released', 'IDLE')
    b = S * 8
    row(b + 14, 'reset in ADD', 'IDLE')
    row(b + 24, 'reset in ADD', 'IDLE')
    for nm, slot in (('op = 000', 9), ('op = 111', 10)):
        b = S * slot
        row(b + 14, nm + ' ignored', 'IDLE')
        row(b + 24, nm + ' ignored', 'IDLE')
    hdr = ['strobe_ns', 'case', 's[2:0]', 'sub', 'arith', 'grp[1:0]', 'fn[1:0]', 'ld_res', 'done']
    emit('t8_fsm_ctrl', sig, rows, hdr, tend)
    TESTS['t8'] = (hdr, rows, tend)


ALU_OPS = [('ADD', 0x00, 0x00), ('ADD', 0xFF, 0x01), ('ADD', 0x7F, 0x01), ('ADD', 0x80, 0x80), ('ADD', 0x0F, 0x01),
           ('ADD', 0x12, 0x34), ('SUB', 0x05, 0x03), ('SUB', 0x03, 0x05), ('SUB', 0x80, 0x01), ('SUB', 0x55, 0x55),
           ('AND', 0xAA, 0x55), ('AND', 0xF0, 0x3C), ('OR', 0xAA, 0x55), ('XOR', 0xF0, 0x3C), ('XOR', 0xFF, 0xFF),
           ('SHL', 0x01, 0x03), ('SHL', 0xFF, 0x04), ('SHL', 0x80, 0x01), ('SHL', 0xA5, 0xF9), ('NOP', 0x55, 0xAA)]


def alu_expected(nm, A, B, prev):
    if nm == 'ADD':
        r, c7, c8 = addsub(A, B, 0)
        return (r, *flags(r, 1, c7, c8))
    if nm == 'SUB':
        r, c7, c8 = addsub(A, B, 1)
        return (r, *flags(r, 1, c7, c8))
    if nm in ('AND', 'OR', 'XOR'):
        r = logic(A, B, ('AND', 'OR', 'XOR').index(nm))
    elif nm == 'SHL':
        r = shl(A, B)
    else:
        return prev
    return (r, *flags(r, 0, 0, 0))


def t9():
    S = 60.0
    n = len(ALU_OPS)
    tend = (n + 1) * S
    sig = {}
    st = [(0.0, 0)]
    for k in range(n):
        t = S * (k + 1)
        st += [(t, 1), (t + 10.0, 0)]
    tt = [0.0] + [S * (k + 1) for k in range(n)]
    Av = [0] + [a for _, a, _ in ALU_OPS]
    Bv = [0] + [b for _, _, b in ALU_OPS]
    Ov = [0] + [OPC.get(nm, 0) for nm, _, _ in ALU_OPS]
    for b in range(8):
        sig['A%d' % b] = [(t, (v >> b) & 1) for t, v in zip(tt, Av)]
    for b in range(8):
        sig['B%d' % b] = [(t, (v >> b) & 1) for t, v in zip(tt, Bv)]
    for b in range(3):
        sig['op%d' % b] = [(t, (v >> b) & 1) for t, v in zip(tt, Ov)]
    sig['start'] = st
    sig['rst'] = [(0.0, 1), (30.0, 0)]
    sig.update(clock_events(tend))
    rows = []
    prev = (0, 0, 0, 0, 0)
    for k, (nm, A, B) in enumerate(ALU_OPS):
        r = alu_expected(nm, A, B, prev)
        prev = r
        rows.append([S * (k + 1) + 24, nm, H(A), H(B), H(r[0]), *r[1:], 0 if nm == 'NOP' else 1])
    hdr = ['strobe_ns', 'op', 'A', 'B', 'result', 'Z', 'N', 'C', 'V', 'done']
    emit('t9_alu8', sig, rows, hdr, tend)
    TESTS['t9'] = (hdr, rows, tend)


def t10():   # D flip-flop with asynchronous reset (clocked, 10 ns slots, rising edge at slot start + 5)
    # (d at slot start, rst at slot start, extra event (dt, signal, value) or None, expected q at slot start + 9, comment)
    slots = [(0, 1, None, 0, 'reset'),
             (1, 1, None, 0, 'reset wins over d'),
             (1, 0, None, 1, 'captures 1'),
             (0, 0, None, 0, 'captures 0'),
             (1, 0, None, 1, 'captures 1'),
             (1, 0, (7, 'd', 0), 1, 'd falls while clk is high: q keeps 1'),
             (0, 0, None, 0, 'captures 0'),
             (1, 0, None, 1, 'captures 1'),
             (1, 0, (7, 'rst', 1), 0, 'reset pulse while clk is high: q falls at once'),
             (1, 0, None, 1, 'captures 1 after reset')]
    tend = len(slots) * SL
    d_ev, r_ev = [], []
    for k, (d, r, ex, q, _) in enumerate(slots):
        t = k * SL
        d_ev.append((t, d))
        r_ev.append((t, r))
        if ex:
            (d_ev if ex[1] == 'd' else r_ev).append((t + ex[0], ex[2]))
        if ex and ex[1] == 'rst':
            r_ev.append((t + 9.5, 0))
    sig = {'d': d_ev, 'rst': r_ev}
    sig.update(clock_events(tend))
    rows = [[k * SL + 9, s[0], s[1], s[4], s[3]] for k, s in enumerate(slots)]
    hdr = ['strobe_ns', 'd (slot start)', 'rst (slot start)', 'what happens', 'q']
    emit('t10_dff_r', sig, rows, hdr, tend)
    TESTS['t10'] = (hdr, rows, tend)


def run():
    for f in (t10, t1, t2, t3, t4, t5, t6, t7, t8, t9):
        f()


if __name__ == '__main__':
    run()
    for k, (h, r, te) in TESTS.items():
        print(k, 'rows:', len(r), ' stop time (ns):', te + 10)
    print('VDD =', VDD)
