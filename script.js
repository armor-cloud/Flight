document.addEventListener('DOMContentLoaded', function() {
    // Инициализация слайдера
    const images = document.querySelectorAll('.prize-image');
    let currentImageIndex = 0;
    let isAnimating = false;

    // Показываем первое изображение
    images[0].classList.add('active');

    // Функция для переключения изображений с плавной анимацией
    function nextImage() {
        if (isAnimating) return;
        isAnimating = true;

        images[currentImageIndex].style.opacity = '0';
        setTimeout(() => {
            images[currentImageIndex].classList.remove('active');
            currentImageIndex = (currentImageIndex + 1) % images.length;
            images[currentImageIndex].classList.add('active');
            images[currentImageIndex].style.opacity = '1';
            isAnimating = false;
        }, 500);
    }

    // Автоматическое переключение изображений каждые 5 секунд
    setInterval(nextImage, 5000);

    // Плавная прокрутка для навигации
    document.querySelectorAll('nav a').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href');
            const targetSection = document.querySelector(targetId);
            const headerOffset = 60;
            const elementPosition = targetSection.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        });
    });

    // Анимация появления элементов при прокрутке
    const observerOptions = {
        threshold: 0.2,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                if (entry.target.classList.contains('prize-slider')) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            }
        });
    }, observerOptions);

    document.querySelectorAll('section, .prize-slider').forEach(element => {
        observer.observe(element);
    });

    // Добавляем эффект параллакса для hero секции
    window.addEventListener('scroll', () => {
        const hero = document.querySelector('.hero');
        const scrolled = window.pageYOffset;
        hero.style.backgroundPositionY = scrolled * 0.5 + 'px';
    });

    // Добавляем активный класс для текущего пункта меню
    const sections = document.querySelectorAll('section');
    const navLinks = document.querySelectorAll('nav a');

    window.addEventListener('scroll', () => {
        let current = '';
        sections.forEach(section => {
            const sectionTop = section.offsetTop;
            const sectionHeight = section.clientHeight;
            if (window.pageYOffset >= sectionTop - 200) {
                current = section.getAttribute('id');
            }
        });

        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('href').slice(1) === current) {
                link.classList.add('active');
            }
        });
    });

    // Динамическая смена глобального фона при скролле
    const bgOverlay = document.getElementById('bg-overlay');
    const sectionsBg = document.querySelectorAll('section[data-bg]');
    let currentBg = '';

    function updateBgOnScroll() {
        let found = false;
        sectionsBg.forEach(section => {
            const rect = section.getBoundingClientRect();
            if (!found && rect.top <= window.innerHeight * 0.4 && rect.bottom > window.innerHeight * 0.2) {
                const bg = section.getAttribute('data-bg');
                if (bg && bg !== currentBg) {
                    bgOverlay.style.backgroundImage = `url('${bg}')`;
                    currentBg = bg;
                }
                found = true;
            }
        });
        if (!found && sectionsBg.length > 0) {
            // fallback на первый фон
            const bg = sectionsBg[0].getAttribute('data-bg');
            if (bg && bg !== currentBg) {
                bgOverlay.style.backgroundImage = `url('${bg}')`;
                currentBg = bg;
            }
        }
    }
    window.addEventListener('scroll', updateBgOnScroll);
    updateBgOnScroll();

    // Слайдер топ-игроков
    const slider = document.querySelector('.top-players-slider');
    if (slider) {
        const track = slider.querySelector('.slider-track');
        const cards = slider.querySelectorAll('.player-card');
        const leftBtn = slider.querySelector('.slider-arrow.left');
        const rightBtn = slider.querySelector('.slider-arrow.right');
        let current = 0;
        let visible = window.innerWidth < 600 ? 1 : window.innerWidth < 900 ? 2 : 3;
        let autoSlide = null;
        let isDragging = false;
        let dragDelta = 0;
        let startX = 0;
        function updateSlider() {
            visible = window.innerWidth < 600 ? 1 : window.innerWidth < 900 ? 2 : 3;
            const cardWidth = cards[0].offsetWidth + 32;
            track.style.transition = '';
            track.style.transform = `translateX(-${current * cardWidth}px)`;
            leftBtn.disabled = current === 0;
            rightBtn.disabled = current >= cards.length - visible;
        }
        function startAutoSlide() {
            if (autoSlide) clearInterval(autoSlide);
            autoSlide = setInterval(() => {
                if (!isDragging) {
                    if (current < cards.length - visible) {
                        current++;
                    } else {
                        current = 0;
                    }
                    updateSlider();
                }
            }, 4000);
        }
        leftBtn.addEventListener('click', () => {
            if (current > 0) current--;
            updateSlider();
        });
        rightBtn.addEventListener('click', () => {
            if (current < cards.length - visible) current++;
            updateSlider();
        });
        window.addEventListener('resize', updateSlider);
        updateSlider();
        startAutoSlide();
        // Drag/Swipe
        track.addEventListener('mousedown', (e) => {
            isDragging = true;
            startX = e.pageX;
            track.style.transition = 'none';
            if (autoSlide) clearInterval(autoSlide);
        });
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            dragDelta = e.pageX - startX;
            track.style.transform = `translateX(${-current * (cards[0].offsetWidth + 32) + dragDelta}px)`;
        });
        document.addEventListener('mouseup', () => {
            if (!isDragging) return;
            isDragging = false;
            track.style.transition = '';
            if (Math.abs(dragDelta) > 50) {
                if (dragDelta < 0 && current < cards.length - visible) current++;
                if (dragDelta > 0 && current > 0) current--;
            }
            dragDelta = 0;
            updateSlider();
            startAutoSlide();
        });
        // Touch
        track.addEventListener('touchstart', (e) => {
            isDragging = true;
            startX = e.touches[0].pageX;
            track.style.transition = 'none';
            if (autoSlide) clearInterval(autoSlide);
        });
        track.addEventListener('touchmove', (e) => {
            if (!isDragging) return;
            dragDelta = e.touches[0].pageX - startX;
            track.style.transform = `translateX(${-current * (cards[0].offsetWidth + 32) + dragDelta}px)`;
        });
        track.addEventListener('touchend', () => {
            if (!isDragging) return;
            isDragging = false;
            track.style.transition = '';
            if (Math.abs(dragDelta) > 50) {
                if (dragDelta < 0 && current < cards.length - visible) current++;
                if (dragDelta > 0 && current > 0) current--;
            }
            dragDelta = 0;
            updateSlider();
            startAutoSlide();
        });
    }

    // Бургер-меню для мобильной версии
    const nav = document.querySelector('nav');
    const menuToggle = document.querySelector('.menu-toggle');
    if (menuToggle) {
        menuToggle.addEventListener('click', function() {
            nav.classList.toggle('open');
        });
        // При клике вне меню — закрывать
        document.addEventListener('click', function(e) {
            if (!nav.contains(e.target) && nav.classList.contains('open')) {
                nav.classList.remove('open');
            }
        });
    }
}); 