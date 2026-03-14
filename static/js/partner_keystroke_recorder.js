/*
 * Partner Keystroke Recorder
 *
 * Single-file integration helper for partner endpoints:
 * - POST /api/partner/enroll
 * - POST /api/partner/verify
 */

'use strict';

var KS_VERSION = '1.0.0';
var KS_MODIFIER_KEYS = {
    Shift: 1,
    Control: 1,
    Alt: 1,
    Meta: 1,
    CapsLock: 1
};
var KS_SPECIAL_KEYS = {
    Backspace: 1,
    Tab: 1,
    ' ': 1
};

function ksNowMs() {
    if (typeof performance !== 'undefined' && performance.now) {
        return performance.now();
    }
    return Date.now();
}

function ksNormalizeKeyCode(event) {
    if (typeof event.keyCode === 'number') {
        return event.keyCode;
    }
    if (typeof event.which === 'number') {
        return event.which;
    }
    return 0;
}

function ksIsEditableTarget(target) {
    if (!target || !target.tagName) {
        return false;
    }

    if (target.isContentEditable) {
        return true;
    }

    var tag = target.tagName.toLowerCase();
    if (tag === 'textarea') {
        return true;
    }

    if (tag === 'input') {
        var type = String(target.type || 'text').toLowerCase();
        return type !== 'button' && type !== 'submit' && type !== 'reset';
    }

    return false;
}

function ksResolveTarget(inputOrSelector) {
    if (!inputOrSelector) {
        throw new Error('Target element or selector is required');
    }

    if (typeof inputOrSelector === 'string') {
        var selector = inputOrSelector;
        var element = document.querySelector(selector);

        if (!element && selector.indexOf('#') !== 0 && selector.indexOf('.') !== 0) {
            element = document.getElementById(selector);
        }

        if (!element) {
            throw new Error('Target not found: ' + selector);
        }

        return element;
    }

    return inputOrSelector;
}

function ksHash32(input) {
    var str = String(input || '').toLowerCase();
    var hash = 0x811c9dc5;
    var i;

    for (i = 0; i < str.length; i += 1) {
        hash ^= str.charCodeAt(i);
        hash +=
            (hash << 1) +
            (hash << 4) +
            (hash << 7) +
            (hash << 8) +
            (hash << 24);
    }

    return hash >>> 0;
}

function ksAverage(values) {
    if (!values || values.length === 0) {
        return 0;
    }

    var sum = 0;
    var i;
    for (i = 0; i < values.length; i += 1) {
        sum += values[i];
    }

    return sum / values.length;
}

function ksStd(values) {
    if (!values || values.length < 2) {
        return 0;
    }

    var mean = ksAverage(values);
    var variance = 0;
    var i;

    for (i = 0; i < values.length; i += 1) {
        var delta = values[i] - mean;
        variance += delta * delta;
    }

    return Math.sqrt(variance / values.length);
}

function ksCloneEvents(events, normalizeTime, maxLength) {
    var source = events;

    if (typeof maxLength === 'number' && maxLength > 0 && source.length > maxLength) {
        source = source.slice(source.length - maxLength);
    }

    if (!normalizeTime || source.length === 0) {
        return source.map(function (evt) {
            return {
                evt: evt.evt,
                key: evt.key,
                code: evt.code,
                keyCode: evt.keyCode,
                t: evt.t,
                seek: evt.seek,
                press: evt.press,
                targetId: evt.targetId,
                isRepeat: !!evt.isRepeat
            };
        });
    }

    var t0 = source[0].t;
    return source.map(function (evt) {
        return {
            evt: evt.evt,
            key: evt.key,
            code: evt.code,
            keyCode: evt.keyCode,
            t: Number((evt.t - t0).toFixed(4)),
            seek: evt.seek,
            press: evt.press,
            targetId: evt.targetId,
            isRepeat: !!evt.isRepeat
        };
    });
}

function ksParsePattern(pattern) {
    if (typeof pattern === 'string') {
        try {
            return JSON.parse(pattern);
        } catch (error) {
            return null;
        }
    }

    if (pattern && typeof pattern === 'object') {
        return pattern;
    }

    return null;
}

function ksComputeQuality(pattern) {
    var parsed = ksParsePattern(pattern);
    if (!parsed || !parsed.metrics) {
        return 0;
    }

    var pairCount = Number(parsed.metrics.pairCount || 0);
    var uniqueKeyCount = Number(parsed.metrics.uniqueKeyCount || 0);
    var pressStd = Number(parsed.metrics.stdPressMs || 0);
    var seekStd = Number(parsed.metrics.stdSeekMs || 0);

    var quantityScore = Math.min(1, pairCount / 25);
    var diversityScore = Math.min(1, uniqueKeyCount / 10);
    var stabilityPenalty = Math.min(1, (pressStd + seekStd) / 300);
    var quality = quantityScore * 0.45 + diversityScore * 0.35 + (1 - stabilityPenalty) * 0.2;

    if (quality < 0) {
        quality = 0;
    }
    if (quality > 1) {
        quality = 1;
    }

    return Number(quality.toFixed(4));
}

function ksDefaultEnvironmentInfo() {
    var nav = typeof navigator !== 'undefined' ? navigator : { userAgent: '' };
    var ua = String(nav.userAgent || '').toLowerCase();
    var browserType = 'unknown';

    if (ua.indexOf('edg/') >= 0) {
        browserType = 'edge';
    } else if (ua.indexOf('firefox') >= 0) {
        browserType = 'firefox';
    } else if (ua.indexOf('opr/') >= 0 || ua.indexOf('opera') >= 0) {
        browserType = 'opera';
    } else if (ua.indexOf('chrome') >= 0) {
        browserType = 'chrome';
    } else if (ua.indexOf('safari') >= 0) {
        browserType = 'safari';
    }

    var isMobile = /android|iphone|ipad|ipod|mobile|tablet/i.test(ua);
    var hasWindow = typeof window !== 'undefined';

    return {
        browserType: browserType,
        isMobile: isMobile,
        hasMotionSensors: hasWindow && typeof window.DeviceMotionEvent !== 'undefined',
        needsPermissionForMotionSensors:
            hasWindow &&
            typeof window.DeviceMotionEvent !== 'undefined' &&
            typeof window.DeviceMotionEvent.requestPermission === 'function'
    };
}

function ksBuildPartnerHeaders(apiKey, extraHeaders) {
    if (!apiKey || !String(apiKey).trim()) {
        throw new Error('apiKey is required');
    }

    var headers = {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + String(apiKey).trim()
    };

    if (extraHeaders && typeof extraHeaders === 'object') {
        Object.keys(extraHeaders).forEach(function (key) {
            headers[key] = extraHeaders[key];
        });
    }

    return headers;
}

function Keystroke(options) {
    if (Keystroke.initialized !== true) {
        if (!(this instanceof Keystroke)) {
            return new Keystroke(options);
        }

        // Main public methods (TypingDNA-style forwarding pattern)
        Keystroke.prototype.start = function () {
            return Keystroke.start.apply(this, arguments);
        };
        Keystroke.prototype.stop = function () {
            return Keystroke.stop.apply(this, arguments);
        };
        Keystroke.prototype.reset = function () {
            return Keystroke.reset.apply(this, arguments);
        };
        Keystroke.prototype.removeEventListeners = function () {
            return Keystroke.removeEventListeners.apply(this, arguments);
        };
        Keystroke.prototype.addTarget = function () {
            return Keystroke.addTarget.apply(this, arguments);
        };
        Keystroke.prototype.removeTarget = function () {
            return Keystroke.removeTarget.apply(this, arguments);
        };
        Keystroke.prototype.getTypingPattern = function () {
            return Keystroke.getTypingPattern.apply(this, arguments);
        };
        Keystroke.prototype.get = function () {
            return Keystroke.get.apply(this, arguments);
        };
        Keystroke.prototype.getQuality = function () {
            return Keystroke.getQuality.apply(this, arguments);
        };
        Keystroke.prototype.getLength = function () {
            return Keystroke.getLength.apply(this, arguments);
        };
        Keystroke.prototype.isMobile = function () {
            return Keystroke.isMobile.apply(this, arguments);
        };
        Keystroke.prototype.getTextId = function () {
            return Keystroke.getTextId.apply(this, arguments);
        };
        Keystroke.prototype.checkEnvironment = function () {
            return Keystroke.checkEnvironment.apply(this, arguments);
        };
        Keystroke.prototype.buildPayload = function () {
            return Keystroke.buildPayload.apply(this, arguments);
        };
        Keystroke.prototype.getEvents = function () {
            return Keystroke.getEvents.apply(this, arguments);
        };
        Keystroke.prototype.hasEnoughData = function () {
            return Keystroke.hasEnoughData.apply(this, arguments);
        };
        Keystroke.prototype.createPartnerApiClient = function () {
            return Keystroke.createPartnerApiClient.apply(this, arguments);
        };
        Keystroke.prototype.bind = function () {
            return Keystroke.bind.apply(this, arguments);
        };

        var opts = options || {};

        Keystroke.initialized = true;
        Keystroke.instance = this;
        Keystroke.version = KS_VERSION;
        Keystroke.maxHistoryLength =
            typeof opts.maxHistoryLength === 'number' && opts.maxHistoryLength > 0
                ? Math.floor(opts.maxHistoryLength)
                : 2000;
        Keystroke.defaultHistoryLength =
            typeof opts.defaultHistoryLength === 'number' && opts.defaultHistoryLength > 0
                ? Math.floor(opts.defaultHistoryLength)
                : 160;
        Keystroke.maxSeekTime =
            typeof opts.maxSeekTime === 'number' && opts.maxSeekTime > 0
                ? Math.floor(opts.maxSeekTime)
                : 2000;
        Keystroke.maxPressTime =
            typeof opts.maxPressTime === 'number' && opts.maxPressTime > 0
                ? Math.floor(opts.maxPressTime)
                : 800;

        Keystroke._minEvents = typeof opts.minEvents === 'number' ? Math.max(1, opts.minEvents) : 4;
        Keystroke._includeModifiers = !!opts.includeModifiers;
        Keystroke._captureSpecialKeys = opts.captureSpecialKeys !== false;
        Keystroke._captureRepeat = opts.captureRepeat !== false;
        Keystroke._normalizeTime = !!opts.normalizeTime;

        Keystroke._recording = false;
        Keystroke._events = [];
        Keystroke._activeKeys = Object.create(null);
        Keystroke._targetMap = Object.create(null);
        Keystroke._targetCount = 0;
        Keystroke._startedAt = null;
        Keystroke._lastKeyDownAt = 0;
        Keystroke._prevKeyCode = 0;

        Keystroke._listenersAttached = false;
        Keystroke._boundKeyDown = function (event) {
            Keystroke._onKeyDown(event);
        };
        Keystroke._boundKeyUp = function (event) {
            Keystroke._onKeyUp(event);
        };

        Keystroke._attachListeners();

        if (Array.isArray(opts.targets)) {
            var i;
            for (i = 0; i < opts.targets.length; i += 1) {
                Keystroke.addTarget(opts.targets[i]);
            }
        }

        if (opts.autoStart !== false) {
            Keystroke.start();
        }
    }

    return Keystroke.instance;
}

Keystroke.initialized = false;
Keystroke.instance = null;
Keystroke.version = KS_VERSION;

Keystroke._attachListeners = function () {
    if (Keystroke._listenersAttached || typeof document === 'undefined' || !document.addEventListener) {
        return;
    }

    document.addEventListener('keydown', Keystroke._boundKeyDown, true);
    document.addEventListener('keyup', Keystroke._boundKeyUp, true);
    Keystroke._listenersAttached = true;
};

Keystroke.removeEventListeners = function () {
    if (!Keystroke._listenersAttached || typeof document === 'undefined' || !document.removeEventListener) {
        return;
    }

    document.removeEventListener('keydown', Keystroke._boundKeyDown, true);
    document.removeEventListener('keyup', Keystroke._boundKeyUp, true);
    Keystroke._listenersAttached = false;
};

Keystroke.start = function () {
    Keystroke._recording = true;
    return Keystroke._recording;
};

Keystroke.stop = function () {
    Keystroke._recording = false;
    return Keystroke._recording;
};

Keystroke.reset = function (all) {
    Keystroke._events = [];
    Keystroke._activeKeys = Object.create(null);
    Keystroke._startedAt = null;
    Keystroke._lastKeyDownAt = 0;
    Keystroke._prevKeyCode = 0;

    if (all === true) {
        Keystroke._targetMap = Object.create(null);
        Keystroke._targetCount = 0;
    }
};

Keystroke.addTarget = function (inputOrSelector) {
    var element = ksResolveTarget(inputOrSelector);

    if (!element.id) {
        element.id = 'partner-keystroke-' + ksHash32(String(ksNowMs()) + Math.random());
    }

    if (!Keystroke._targetMap[element.id]) {
        Keystroke._targetMap[element.id] = true;
        Keystroke._targetCount += 1;
    }

    return element.id;
};

Keystroke.removeTarget = function (inputOrSelector) {
    var targetId = null;

    if (typeof inputOrSelector === 'string') {
        targetId = inputOrSelector;
        if (targetId.charAt(0) === '#') {
            targetId = targetId.slice(1);
        }
    } else if (inputOrSelector && inputOrSelector.id) {
        targetId = inputOrSelector.id;
    }

    if (targetId && Keystroke._targetMap[targetId]) {
        delete Keystroke._targetMap[targetId];
        Keystroke._targetCount -= 1;
    }
};

Keystroke._isTargetAllowed = function (target) {
    if (!ksIsEditableTarget(target)) {
        return false;
    }

    if (Keystroke._targetCount === 0) {
        return true;
    }

    var targetId = target && target.id ? target.id : '';
    return !!(targetId && Keystroke._targetMap[targetId]);
};

Keystroke._isEventAllowed = function (event) {
    if (!Keystroke._recording) {
        return false;
    }

    if (!event || !Keystroke._isTargetAllowed(event.target)) {
        return false;
    }

    if (event.key === 'Enter') {
        return false;
    }

    var isModifier = !!KS_MODIFIER_KEYS[event.key];
    if (!Keystroke._includeModifiers && isModifier) {
        return false;
    }

    if (event.key && event.key.length > 1 && !isModifier) {
        if (!Keystroke._captureSpecialKeys || !KS_SPECIAL_KEYS[event.key]) {
            return false;
        }
    }

    return true;
};

Keystroke._onKeyDown = function (event) {
    if (!Keystroke._isEventAllowed(event)) {
        return;
    }

    var timestamp = ksNowMs();
    var keyIdentity = event.code || event.key || 'unknown';

    if (!Keystroke._captureRepeat && Keystroke._activeKeys[keyIdentity]) {
        return;
    }

    if (Keystroke._startedAt === null) {
        Keystroke._startedAt = timestamp;
    }

    var seekTime = Keystroke._lastKeyDownAt > 0 ? timestamp - Keystroke._lastKeyDownAt : 0;
    Keystroke._lastKeyDownAt = timestamp;

    Keystroke._activeKeys[keyIdentity] = {
        startedAt: timestamp,
        keyCode: ksNormalizeKeyCode(event)
    };

    Keystroke._events.push({
        evt: 'd',
        key: event.key,
        code: event.code,
        keyCode: ksNormalizeKeyCode(event),
        t: timestamp,
        seek: Math.round(seekTime),
        prevKeyCode: Keystroke._prevKeyCode,
        targetId: event.target && event.target.id ? event.target.id : '',
        isRepeat: !!event.repeat
    });

    if (Keystroke._events.length > Keystroke.maxHistoryLength) {
        Keystroke._events.shift();
    }
};

Keystroke._onKeyUp = function (event) {
    if (!Keystroke._isEventAllowed(event)) {
        return;
    }

    var keyIdentity = event.code || event.key || 'unknown';
    var activeState = Keystroke._activeKeys[keyIdentity];
    if (!activeState) {
        return;
    }

    delete Keystroke._activeKeys[keyIdentity];

    var timestamp = ksNowMs();
    var pressTime = timestamp - activeState.startedAt;
    if (pressTime < 0) {
        pressTime = 0;
    }

    var currentKeyCode = ksNormalizeKeyCode(event);
    Keystroke._events.push({
        evt: 'u',
        key: event.key,
        code: event.code,
        keyCode: currentKeyCode,
        t: timestamp,
        press: Math.round(pressTime),
        targetId: event.target && event.target.id ? event.target.id : '',
        isRepeat: false
    });

    Keystroke._prevKeyCode = currentKeyCode;

    if (Keystroke._events.length > Keystroke.maxHistoryLength) {
        Keystroke._events.shift();
    }
};

Keystroke.getEvents = function (options) {
    var opts = options || {};
    var maxLength = typeof opts.length === 'number' ? opts.length : null;
    var normalizeTime =
        typeof opts.normalizeTime === 'boolean' ? opts.normalizeTime : Keystroke._normalizeTime;

    return ksCloneEvents(Keystroke._events, normalizeTime, maxLength);
};

Keystroke.getEventCount = function () {
    return Keystroke._events.length;
};

Keystroke.hasEnoughData = function (minEvents) {
    var threshold = typeof minEvents === 'number' ? minEvents : Keystroke._minEvents;
    return Keystroke._events.length >= threshold;
};

Keystroke.getElapsedSeconds = function () {
    if (Keystroke._startedAt === null) {
        return 0;
    }
    return (ksNowMs() - Keystroke._startedAt) / 1000;
};

Keystroke._buildPairRows = function (events) {
    var pending = Object.create(null);
    var pairs = [];

    events.forEach(function (evt) {
        var identity = evt.code || evt.key || 'unknown';

        if (evt.evt === 'd') {
            if (!pending[identity]) {
                pending[identity] = [];
            }
            pending[identity].push(evt);
            return;
        }

        if (evt.evt === 'u' && pending[identity] && pending[identity].length > 0) {
            var down = pending[identity].shift();
            var press = typeof evt.press === 'number' ? evt.press : Math.max(0, evt.t - down.t);
            pairs.push({
                keyCode: down.keyCode,
                key: down.key,
                seek: Math.max(0, Number(down.seek || 0)),
                press: Math.max(0, Number(press || 0)),
                targetId: down.targetId || ''
            });
        }
    });

    return pairs;
};

Keystroke._buildMetrics = function (pairs) {
    var seekSeries = [];
    var pressSeries = [];
    var uniqueKeys = Object.create(null);

    pairs.forEach(function (item) {
        if (item.seek <= 10000) {
            seekSeries.push(item.seek);
        }
        if (item.press <= 10000) {
            pressSeries.push(item.press);
        }
        uniqueKeys[item.keyCode || item.key || '0'] = true;
    });

    var elapsed = Keystroke.getElapsedSeconds();
    var cpm = elapsed > 0 ? Math.round((pairs.length * 60) / elapsed) : 0;

    return {
        eventCount: Keystroke._events.length,
        pairCount: pairs.length,
        uniqueKeyCount: Object.keys(uniqueKeys).length,
        avgSeekMs: Number(ksAverage(seekSeries).toFixed(4)),
        avgPressMs: Number(ksAverage(pressSeries).toFixed(4)),
        stdSeekMs: Number(ksStd(seekSeries).toFixed(4)),
        stdPressMs: Number(ksStd(pressSeries).toFixed(4)),
        cpm: cpm,
        elapsedSeconds: Number(elapsed.toFixed(3))
    };
};

Keystroke.getTypingPattern = function (options) {
    var opts = options || {};
    var type = typeof opts.type === 'number' ? opts.type : 2;
    var length = typeof opts.length === 'number' ? opts.length : Keystroke.defaultHistoryLength;
    var text = typeof opts.text === 'string' ? opts.text : '';

    var events = Keystroke.getEvents({ length: length, normalizeTime: false });
    var pairs = Keystroke._buildPairRows(events);
    var metrics = Keystroke._buildMetrics(pairs);

    var pattern = {
        sdk: 'partner-keystroke',
        version: Keystroke.version,
        type: type,
        textId: Keystroke.getTextId(text),
        textLength: text.length,
        metrics: metrics,
        entries: pairs
    };

    if (opts.asObject === true) {
        return pattern;
    }

    return JSON.stringify(pattern);
};

Keystroke.get = function () {
    return Keystroke.getTypingPattern.apply(Keystroke, arguments);
};

Keystroke.getQuality = function (pattern) {
    return ksComputeQuality(pattern);
};

Keystroke.getLength = function (pattern) {
    var parsed = ksParsePattern(pattern);
    if (parsed && parsed.metrics) {
        return Number(parsed.metrics.pairCount || 0);
    }

    return Number(Keystroke._buildPairRows(Keystroke._events).length || 0);
};

Keystroke.isMobile = function () {
    return ksDefaultEnvironmentInfo().isMobile ? 1 : 0;
};

Keystroke.checkEnvironment = function () {
    return ksDefaultEnvironmentInfo();
};

Keystroke.getTextId = function (text) {
    return ksHash32(String(text || ''));
};

Keystroke.buildPayload = function (params) {
    var options = params || {};
    if (!options.username || !String(options.username).trim()) {
        throw new Error('username is required when building partner payload');
    }

    return {
        username: String(options.username).trim(),
        email: options.email ? String(options.email).trim() : undefined,
        password: options.password ? String(options.password) : undefined,
        password_hash: options.passwordHash ? String(options.passwordHash) : undefined,
        events: Keystroke.getEvents({ normalizeTime: Keystroke._normalizeTime })
    };
};

Keystroke.createPartnerApiClient = function (options) {
    var opts = options || {};
    var baseUrl = opts.baseUrl || '/api/partner';
    var apiKey = opts.apiKey;
    var fetchImpl = opts.fetchImpl;

    if (!fetchImpl && typeof fetch !== 'undefined') {
        fetchImpl = fetch.bind(typeof window !== 'undefined' ? window : null);
    }

    if (!fetchImpl) {
        throw new Error('fetch API is not available in this environment');
    }

    async function request(path, payload, requestOptions) {
        var extraHeaders = requestOptions && requestOptions.headers ? requestOptions.headers : null;
        var response = await fetchImpl(baseUrl + path, {
            method: 'POST',
            headers: ksBuildPartnerHeaders(apiKey, extraHeaders),
            body: JSON.stringify(payload || {}),
            credentials:
                requestOptions && requestOptions.credentials ? requestOptions.credentials : 'omit'
        });

        var jsonBody = null;
        try {
            jsonBody = await response.json();
        } catch (error) {
            jsonBody = {
                success: false,
                message: 'Failed to parse API response JSON'
            };
        }

        if (!response.ok) {
            var wrappedError = new Error(
                (jsonBody && jsonBody.message) || 'Partner API request failed'
            );
            wrappedError.status = response.status;
            wrappedError.payload = jsonBody;
            throw wrappedError;
        }

        return jsonBody;
    }

    return {
        enroll: function (payload, requestOptions) {
            return request('/enroll', payload, requestOptions);
        },
        verify: function (payload, requestOptions) {
            return request('/verify', payload, requestOptions);
        }
    };
};

Keystroke.bind = function (inputOrSelector, options) {
    var recorder = new Keystroke(options || {});
    recorder.addTarget(inputOrSelector);
    return recorder;
};

if (typeof window !== 'undefined') {
    window.Keystroke = Keystroke;
}
