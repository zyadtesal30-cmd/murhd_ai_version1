# -*- coding: utf-8 -*-
"""مساعد محلي (Offline) — بيفهم أسئلة الطالب بالعربي ويجاوب من بياناته ولائحة القسم من غير إنترنت.
مفيش نموذج ذكاء اصطناعي خارجي: فهم الأسئلة بالكلمات المفتاحية + مطابقة تقريبية لأسماء المواد،
والإجابات كلها محسوبة من نفس محرك التطبيق (المعدل، الخطة، المتطلبات، هدف المعدل)."""
import difflib
import re

import engine as E

_DIAC = re.compile('[\u064B-\u065F\u0670\u0640]')
_PUNCT = re.compile(r'[^\w\s.+\-]', re.U)
_INTENT = set('تخرج اتخرج معدل معدلي ساعه ساعات فصل جاي قادم متبقي فاضل باقي شروط لائحه تقدير'.split())
_STOP = set('في من الي على عن ان هل ما ماذا ايه اي انا لو ده دي يا مع او ثم كل بعد قبل هو هي كام عايز عاوز اريد'.split())

SUGGEST = ['معدلي كام؟', 'فاضل لي كام ساعة؟', 'أسجل إيه الفصل الجاي؟', 'إيه اللي بيأخّرني؟',
           'عايز أتخرج بمعدل 3.5', 'شروط التخرج', 'ايه هي مرتبة الشرف؟']


def norm(s):
    s = str(s).translate(E.AR_DIGITS).lower()
    s = _DIAC.sub('', s)
    for a, b in (('أ', 'ا'), ('إ', 'ا'), ('آ', 'ا'), ('ٱ', 'ا'), ('ى', 'ي'), ('ة', 'ه'), ('ؤ', 'و'), ('ئ', 'ي'),
                 ('٫', '.'), ('،', ' '), ('؟', ' ')):
        s = s.replace(a, b)
    return _PUNCT.sub(' ', s)


def toks(s):
    out = []
    for t in norm(s).split():
        if t.startswith('ال') and len(t) > 4:
            t = t[2:]
        out.append(t)
    return out


_CN = {c.code: set(toks(c.name)) for c in E.COURSES}
_CODE = {re.sub(r'\s+', '', c.code.lower()): c.code for c in E.COURSES}


def find_courses(text):
    """يرجّع (قايمة مواد مطابقة, هل الرقم اتحدد)."""
    n = norm(text)
    flat = re.sub(r'\s+', '', n)
    for k, code in _CODE.items():           # كود كامل مثل MREn 424 أو mren424
        if k in flat:
            return [E.C[code]], True
    m = re.search(r'\b(\d{3})\b', n)         # رقم المقرر بس: 424
    if m:
        hit = [c for c in E.COURSES if c.code.endswith(m.group(1))]
        if len(hit) == 1:
            return hit, True
    ut = [t for t in toks(text) if t not in _STOP]
    words = {t for t in ut if not t.isdigit() and len(t) >= 3 and t not in _INTENT}
    nums = {t for t in ut if t.isdigit() and len(t) == 1}
    if not words:
        return [], False
    scored = []
    for c in E.COURSES:
        ct = _CN[c.code]
        cw = {t for t in ct if not t.isdigit()}
        if not cw:
            continue
        hit = 0.0
        for w in words:
            if w in cw:
                hit += 1
            else:
                best = max((difflib.SequenceMatcher(None, w, x).ratio() for x in cw), default=0)
                if best >= 0.84:
                    hit += best
        if hit < 1:
            continue
        sc = hit / len(words) + 0.01 * hit / len(cw)      # نسبة كلمات سؤالك اللي لقيناها في اسم المادة
        cn = {t for t in ct if t.isdigit()}
        if nums and cn:
            sc += 0.5 if (nums & cn) else -0.3
        scored.append((sc, c))
    if not scored:
        return [], False
    scored.sort(key=lambda x: -x[0])
    top = scored[0][0]
    if top < 0.6:
        return [], False
    best = [c for sc, c in scored if sc >= top - 0.01]
    return best[:5], bool(nums) and len(best) == 1 or len(best) == 1


def _gpa_parts(p):
    an = p['an']
    if an.get('gpa_calc') is not None:
        return an['gpa_calc'] * an['gpa_hours'], an['gpa_hours']
    if an.get('gpa') is not None:
        h = float(sum(c.cr for c in E.COURSES if p['st'].passed(c.code)))
        return an['gpa'] * h, h
    return 0.0, 0.0


def _status(c, st):
    s = st.s(c.code)
    if s == 'done':
        g = st.g(c.code)
        return 'راسب (F)' if g == 'F' else ('خلّصتها' + (' بتقدير %s' % g if g else ''))
    if s == 'cur':
        return 'بتدرسها الآن'
    return 'لسه ما أخدتهاش'


def _term_credits(t):
    return sum(E.C[x].cr for x in t['codes'])


# ───────────── الإجابات ─────────────
def a_gpa(p):
    an = p['an']
    g = an['gpa']
    if g is None:
        return 'لسه مفيش تقديرات مدخلة. ادخل تقديراتك في «موادي» أو اكتب معدلك في «بياناتي» وأحسبهولك.'
    L = ['معدلك التراكمي: %.2f%s' % (g, ' (على %d ساعة)' % an['gpa_hours'] if an['gpa_hours'] else ' (مدخل يدوي)')]
    if an['probation']:
        L.append('⚠ معدلك أقل من 2.00 — إنت تحت الملاحظة والحد الأقصى للتسجيل %d ساعة.' % E.PROBATION_LOAD)
    elif g >= 3.3 and not an['fail']:
        L.append('✔ إنت في نطاق مرتبة الشرف (3.3 فأكثر بشرط عدم الرسوب في أي مقرر).')
    elif g >= 3.3:
        L.append('معدلك في نطاق الشرف لكن الرسوب في مقرر بيمنع مرتبة الشرف.')
    else:
        L.append('ناقصك %.2f نقطة عشان توصل لحد مرتبة الشرف (3.3).' % (3.3 - g))
    if an['fail']:
        L.append('راسب في: ' + '، '.join(c.name for c in an['fail']))
    return '\n'.join(L)


def a_grad(p):
    an, my = p['an'], p['my']
    done_h = an['counted'] + an['cur_hours']
    L = ['منجز %d ساعة من %d (%d%%) — فاضل %d ساعة.' % (done_h, E.TOTAL_REQUIRED, 100 * done_h // E.TOTAL_REQUIRED, an['remaining'])]
    if my is not None:
        if my['terms']:
            L.append('التخرج المتوقع: %s بعد %d فصل.' % (my['finish_label'], my['n_terms']))
        else:
            L.append('خلّصت متطلبات الخطة — راجع شروط التخرج (التدريب والمعدل).')
    return '\n'.join(L)


def a_next(p):
    my = p['my']
    if not my or not my['terms']:
        return 'مفيش مواد متبقية في الخطة الحالية.'
    t = my['terms'][0]
    L = ['الفصل الجاي (%s) — %d ساعة:' % (t['label'], _term_credits(t))]
    for code in t['codes']:
        c = E.C[code]
        L.append('• %s (%d)%s' % (c.name, c.cr, ' — إعادة' if p['st'].failed(code) else ''))
    L.append('تفاصيل أكتر وبدائل في تبويب «خطتي».')
    return '\n'.join(L)


def a_diag(p):
    kind = {'ok': '✔ ', 'warn': '⚠ ', 'bad': '✘ ', 'info': '• '}
    return '\n'.join(kind.get(k, '• ') + m for k, m in p['diag']) or 'مفيش حاجة بتأخّرك.'


def a_check(p):
    sym = {'ok': '✔', 'no': '✘', 'unk': '؟', 'wait': '…'}
    return '\n'.join('%s %s — %s' % (sym.get(s, '•'), t, d) for t, s, d in p['check'])


def a_course(c, p):
    st, cfg = p['st'], p['cfg']
    L = ['%s (%s)' % (c.name, c.code),
         '%d ساعة • %s • %s • الفصل المقترح %s' % (c.cr, 'إجباري' if c.kind == 'R' else 'اختياري', E.KIND_TXT[c.grp], c.sem or '—'),
         'حالتك: ' + _status(c, st)]
    pre = E.pre_of(c.code, cfg)
    if pre:
        L.append('المتطلبات السابقة:')
        for x in pre:
            L.append('  %s %s' % ('✔' if st.satisfied(x) else '✘', E.C[x].name))
    else:
        L.append('مفيش متطلبات سابقة.')
    nxt = [d.name for d in E.COURSES if c.code in E.pre_of(d.code, cfg)]
    if nxt:
        L.append('بتفتح لك: ' + '، '.join(nxt))
    if not st.passed(c.code) and not st.cur(c.code):
        row = [r for cc, r in p['elig'] if cc.code == c.code]
        if row:
            L.append('تقدر تسجلها دلوقتي ✔' if not row[0] else 'مش متاحة دلوقتي: ' + ' / '.join(row[0]))
    return '\n'.join(L)


def a_prereq(c, p):
    pre = E.pre_of(c.code, p['cfg'])
    if not pre:
        return '%s مالهاش متطلبات سابقة.' % c.name
    return 'متطلبات %s:\n' % c.name + '\n'.join('%s %s' % ('✔' if p['st'].satisfied(x) else '✘', E.C[x].name) for x in pre)


_LETTER = re.compile(r'(?<![a-z])([abcdf][+-]?)(?![a-z])')


def a_whatif(c, letter, p):
    pts = E.GRADES.get(letter.upper())
    if pts is None:
        return 'التقدير غير معروف. المتاح: ' + ' '.join(E.GRADE_LIST)
    num, den = _gpa_parts(p)
    st = p['st']
    if st.s(c.code) == 'done' and st.g(c.code) in E.GRADES:     # إعادة/تحسين: شيل التقدير القديم
        num -= E.GRADES[st.g(c.code)] * c.cr
        den -= c.cr
    if st.failed(c.code):
        pts = min(pts, E.RETAKE_CAP)
    new = (num + pts * c.cr) / (den + c.cr) if den + c.cr else None
    now = p['an']['gpa']
    out = 'لو جبت %s في %s (%d ساعة) معدلك هيبقى %.2f' % (letter.upper(), c.name, c.cr, new)
    if now is not None:
        out += ' بدل %.2f (%+.2f).' % (now, new - now)
    if st.failed(c.code):
        out += '\n(الراسب بيتحسب له C كحد أقصى عند الإعادة)'
    return out


def a_goal(target, p):
    r = E.goal_plan(p, target)
    if r['empty']:
        return 'مفيش مواد متبقية — معدلك النهائي %s.' % ('%.2f' % r['base_gpa'] if r['base_gpa'] is not None else '—')
    if not r['feasible']:
        return 'مش ممكن توصل %.2f — أقصى معدل %.2f لو جبت أعلى تقدير في كل الباقي.' % (target, r['max_gpa'])
    dist = {}
    for it in r['items']:
        n, h = dist.get(it['letter'], (0, 0))
        dist[it['letter']] = (n + 1, h + it['cr'])
    parts = ['%s في %d مادة' % (l, dist[l][0]) for l, _g in reversed(E.GRADE_STEPS) if l in dist]
    return ('ممكن توصل %.2f ✔\nمحتاج متوسط حوالي %.2f في باقي المواد (%d مادة = %d ساعة).\nالتوزيع: %s.\n'
            'تفاصيل كل مادة في «خطتي ← هدف المعدل».') % (target, r['need_avg'], r['n'], r['hours'], '، '.join(parts))


# ───────────── قواعد اللائحة ─────────────
def _rules():
    out, cur = [], ''
    for ln in E.RULES_TEXT.splitlines():
        if ln.startswith('•'):
            if cur:
                out.append(cur)
            cur = ln[1:].strip()
        elif ln.startswith('  ') and cur:
            cur += ' ' + ln.strip()
        else:
            if cur:
                out.append(cur)
            cur = ''
    if cur:
        out.append(cur)
    return out


_RULES = _rules()
_SYN = {'غياب': 'حضور', 'حمل': 'ساعات', 'اعاده': 'اعيد', 'رسوب': 'راسب', 'امتياز': 'شرف', 'سنين': 'سنوات'}


def a_rules(text):
    q = {_SYN.get(t, t) for t in toks(text) if t not in _STOP and len(t) >= 3}
    best = []
    for r in _RULES:
        rt = set(toks(r))
        sc = sum(1 for t in q if any(t == x or (len(t) >= 4 and len(x) >= 4 and (t in x or x in t)) for x in rt))
        if sc:
            best.append((sc, r))
    best.sort(key=lambda x: -x[0])
    if not best:
        return None
    return '\n'.join('• ' + r for _s, r in best[:2])


# ───────────── الموجّه ─────────────
def _has(n, *words):
    return any(w in n for w in words)


def answer(text, p):
    """(نص الرد, اقتراحات متابعة)."""
    raw = str(text).strip()
    n = norm(raw)
    if not n.strip():
        return 'اكتب سؤالك وأنا أجاوبك.', SUGGEST
    if _has(n, 'اهلا', 'مرحبا', 'السلام', 'هاي', 'صباح', 'مساء') and len(n.split()) <= 3:
        return 'أهلاً! أنا مساعدك الأكاديمي (بشتغل من غير إنترنت). اسألني عن معدلك أو خطتك أو أي مادة أو اللائحة.', SUGGEST
    if _has(n, 'ساعد', 'تقدر', 'بتعمل', 'بتعرف', 'help', 'ايه الاوامر'):
        return ('أقدر أجاوبك عن:\n• معدلك وحالتك (تحت الملاحظة/الشرف)\n• المتبقي والتخرج المتوقع\n• تسجّل إيه الفصل الجاي\n'
                '• أي مادة: متطلباتها وحالتك فيها\n• «لو جبت A في رياضيات 2 معدلي هيبقى كام؟»\n'
                '• «عايز أتخرج بمعدل 3.5» وأقولك تجيب كام في كل مادة\n• قواعد اللائحة (حضور، صيفي، إعادة...)'), SUGGEST

    courses, exact = find_courses(raw)
    lm = _LETTER.search(raw.lower().translate(E.AR_DIGITS))
    low = raw.translate(E.AR_DIGITS).replace('٫', '.').replace(',', '.')
    nums = [float(x) for x in re.findall(r'(?<![\d.])([1-4](?:\.\d{1,2})?)(?![\d])', low)]
    goal_words = _has(n, 'هدف', 'اتخرج', 'تخرج بمعدل', 'عايز', 'عاوز', 'محتاج', 'اجيب', 'وصل', 'ارفع', 'اوصل', 'شرف')
    cn = [x for x in nums if 1.0 <= x <= 4.0]

    # لو جبت X في مادة
    if lm and courses and _has(n, 'لو', 'اذا', 'جبت', 'اخد', 'هجيب', 'تقدير'):
        if len(courses) == 1:
            return a_whatif(courses[0], lm.group(1), p), []
        return 'تقصد أنهي مادة؟ ' + '، '.join(c.name for c in courses), []
    # هدف المعدل
    if goal_words and not courses and not cn and any(x > 4 or x < 1 for x in [float(v) for v in re.findall(r'\d+(?:\.\d+)?', low)]):
        return 'المعدل لازم يكون بين 1 و 4 (مثلاً: عايز أتخرج بمعدل 3.5).', []
    if cn and goal_words and not courses:
        return a_goal(cn[0], p), []
    if lm and goal_words and not courses and E.GRADES.get(lm.group(1).upper()):
        return a_goal(E.GRADES[lm.group(1).upper()], p), []
    if _has(n, 'مرتبه الشرف', 'مرتبة الشرف') and not _has(n, 'عايز', 'عاوز'):
        a = a_rules(raw)
        return (a or 'مرتبة الشرف: معدل 3.3 فأكثر بشرط عدم الرسوب في أي مقرر.'), []
    if _has(n, 'شرف') and goal_words:
        return a_goal(3.3, p), []

    if courses:
        if len(courses) > 1 and not exact:
            return 'تقصد أنهي مادة؟\n' + '\n'.join('• %s (%s)' % (c.name, c.code) for c in courses), []
        c = courses[0]
        if _has(n, 'متطلب', 'prereq', 'محتاج الاول', 'قبل'):
            return a_prereq(c, p), []
        return a_course(c, p), []

    if _has(n, 'راسب', 'رسبت', 'f '):
        f = p['an']['fail']
        return ('راسب في: ' + '، '.join(c.name for c in f) + '\nلازم تعيدها (وبتتحسب C كحد أقصى).') if f else 'مفيش مواد راسب فيها ✔', []
    if _has(n, 'بدرس', 'الحاليه', 'الحالي'):
        cur = p['an']['cur']
        return ('بتدرس دلوقتي:\n' + '\n'.join('• %s (%d)' % (c.name, c.cr) for c in cur)) if cur else 'مفيش مواد معلّمة «بدرسها الآن».', []
    if _has(n, 'معدل', 'gpa', 'تراكمي') and not _has(n, 'شروط'):
        return a_gpa(p), []
    if _has(n, 'شروط', 'شرط', 'متطلبات التخرج', 'اخلص', 'خلصت'):
        return a_check(p), []
    if _has(n, 'صيف'):
        r = a_rules(raw)
        if r:
            return r, []
    if _has(n, 'الفصل الجاي', 'الترم الجاي', 'الفصل القادم', 'اسجل', 'هسجل', 'ادرس ايه', 'اخد ايه', 'اخد اي', 'سجل'):
        return a_next(p), []
    if _has(n, 'ياخر', 'اتاخر', 'تاخير', 'ليه', 'مشكل', 'اخر'):
        return a_diag(p), []
    if _has(n, 'تخرج', 'فاضل', 'متبقي', 'باقي', 'ساعات', 'نسبه', 'انجاز'):
        return a_grad(p), []

    r = a_rules(raw)
    if r:
        return r, []
    return ('مش متأكد فهمت سؤالك 🤔 جرّب تسأل عن: معدلك، المتبقي للتخرج، تسجّل إيه الفصل الجاي، أي مادة بالاسم، '
            'أو «عايز أتخرج بمعدل 3.5».'), SUGGEST
