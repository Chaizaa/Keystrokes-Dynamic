(function () {
    "use strict";

    function initTime() {
        function updateTime() {
            var now = new Date();
            var iso = now.toISOString().replace("T", " ").slice(0, 19) + "Z";

            var liveTime = document.getElementById("live-time");
            if (liveTime) {
                liveTime.textContent = iso;
            }

            var yearEl = document.getElementById("current-year");
            if (yearEl) {
                yearEl.textContent = String(now.getFullYear());
            }
        }

        updateTime();
        window.setInterval(updateTime, 1000);
    }

    function initReveal() {
        var revealElements = document.querySelectorAll(".reveal");
        if (!revealElements.length) {
            return;
        }

        if (!("IntersectionObserver" in window)) {
            revealElements.forEach(function (el) {
                el.classList.add("active");
            });
            return;
        }

        var observer = new IntersectionObserver(
            function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("active");
                    }
                });
            },
            { threshold: 0.1, rootMargin: "0px 0px -50px 0px" }
        );

        revealElements.forEach(function (el) {
            observer.observe(el);
        });
    }

    function initCounters() {
        var counters = document.querySelectorAll(".counter");
        if (!counters.length) {
            return;
        }

        function animateCounter(el) {
            var target = parseInt(el.getAttribute("data-target"), 10);
            if (!Number.isFinite(target)) {
                return;
            }

            var current = 0;
            var increment = target / 40;

            function step() {
                current += increment;
                if (current < target) {
                    el.textContent = String(Math.ceil(current));
                    window.requestAnimationFrame(step);
                } else {
                    el.textContent = String(target);
                }
            }

            step();
        }

        if (!("IntersectionObserver" in window)) {
            counters.forEach(animateCounter);
            return;
        }

        var observer = new IntersectionObserver(
            function (entries, obs) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        animateCounter(entry.target);
                        obs.unobserve(entry.target);
                    }
                });
            },
            { threshold: 0.5 }
        );

        counters.forEach(function (counter) {
            observer.observe(counter);
        });
    }

    function initDataMesh() {
        var canvas = document.getElementById("data-mesh");
        var hero = document.querySelector(".landing-hero");
        if (!canvas || !hero) {
            return;
        }

        var ctx = canvas.getContext("2d");
        if (!ctx) {
            return;
        }

        var width = 0;
        var height = 0;
        var dpr = window.devicePixelRatio || 1;
        var nodes = [];
        var mouse = { x: -1000, y: -1000 };

        function resizeCanvas() {
            dpr = window.devicePixelRatio || 1;
            width = hero.clientWidth;
            height = hero.clientHeight;

            canvas.width = Math.max(1, Math.floor(width * dpr));
            canvas.height = Math.max(1, Math.floor(height * dpr));
            canvas.style.width = width + "px";
            canvas.style.height = height + "px";

            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }

        function Node(x, y) {
            this.baseX = x;
            this.baseY = y;
            this.x = x;
            this.y = y;
            this.vx = (Math.random() - 0.5) * 0.5;
            this.vy = (Math.random() - 0.5) * 0.5;
            this.size = Math.random() * 1.5 + 0.5;
        }

        Node.prototype.update = function () {
            this.baseX += this.vx;
            this.baseY += this.vy;

            if (this.baseX < 0) this.baseX = width;
            if (this.baseX > width) this.baseX = 0;
            if (this.baseY < 0) this.baseY = height;
            if (this.baseY > height) this.baseY = 0;

            var dx = mouse.x - this.baseX;
            var dy = mouse.y - this.baseY;
            var dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 200) {
                var force = (200 - dist) / 200;
                this.x = this.baseX - dx * force * 0.3;
                this.y = this.baseY - dy * force * 0.3;
            } else {
                this.x = this.baseX;
                this.y = this.baseY;
            }
        };

        Node.prototype.draw = function () {
            ctx.fillStyle = "rgba(255, 122, 42, 0.4)";
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fill();
        };

        function createNodes() {
            nodes = [];
            var spacing = 60;
            var cols = Math.floor(width / spacing);
            var rows = Math.floor(height / spacing);

            for (var i = 0; i < cols; i += 1) {
                for (var j = 0; j < rows; j += 1) {
                    var ox = (Math.random() - 0.5) * 20;
                    var oy = (Math.random() - 0.5) * 20;
                    nodes.push(new Node(i * spacing + ox, j * spacing + oy));
                }
            }
        }

        function draw() {
            ctx.clearRect(0, 0, width, height);
            ctx.lineWidth = 0.5;

            for (var i = 0; i < nodes.length; i += 1) {
                nodes[i].update();
                nodes[i].draw();

                for (var j = i + 1; j < nodes.length; j += 1) {
                    var dx = nodes[i].x - nodes[j].x;
                    var dy = nodes[i].y - nodes[j].y;
                    var dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < 80) {
                        ctx.beginPath();
                        ctx.strokeStyle = "rgba(255, 255, 255, " + (0.1 * (1 - dist / 80)) + ")";
                        ctx.moveTo(nodes[i].x, nodes[i].y);
                        ctx.lineTo(nodes[j].x, nodes[j].y);
                        ctx.stroke();
                    }
                }

                var mdx = mouse.x - nodes[i].x;
                var mdy = mouse.y - nodes[i].y;
                var mouseDist = Math.sqrt(mdx * mdx + mdy * mdy);
                if (mouseDist < 150) {
                    ctx.beginPath();
                    ctx.strokeStyle = "rgba(255, 122, 42, " + (0.4 * (1 - mouseDist / 150)) + ")";
                    ctx.moveTo(nodes[i].x, nodes[i].y);
                    ctx.lineTo(mouse.x, mouse.y);
                    ctx.stroke();
                }
            }

            var scanY = (Date.now() / 20) % height;
            ctx.fillStyle = "rgba(255, 122, 42, 0.05)";
            ctx.fillRect(0, scanY, width, 2);
            ctx.fillStyle = "rgba(255, 122, 42, 0.02)";
            ctx.fillRect(0, scanY - 10, width, 10);

            window.requestAnimationFrame(draw);
        }

        hero.addEventListener("mousemove", function (e) {
            var rect = canvas.getBoundingClientRect();
            mouse.x = e.clientX - rect.left;
            mouse.y = e.clientY - rect.top;
        });

        hero.addEventListener("mouseleave", function () {
            mouse.x = -1000;
            mouse.y = -1000;
        });

        window.addEventListener("resize", function () {
            resizeCanvas();
            createNodes();
        });

        resizeCanvas();
        createNodes();
        draw();
    }

    document.addEventListener("DOMContentLoaded", function () {
        initTime();
        initReveal();
        initCounters();
        initDataMesh();
    });
})();

