/*
 * GaW-Vertretungsplan
 * Copyright (C) 2019-2021  Florian Rädiker
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

const gulp = require("gulp");
const sourcemaps = require("gulp-sourcemaps");
const rename = require("gulp-rename");
const fs = require("fs");


const ASSETS_PATH = "static_src/";
const DEST = "static/";

const SUBSTITUTIONS_BUNDLE_FILES = [
    "substitutions-base.js",
    "grey-substitutions.js",
    "highlight-new-substitutions.js",
    "push-notifications.js",
    "updates.js",
    "themes.js",
    "plausible.js"
];

const JS_SRC = ["static_src/**/*.js", "!"+ASSETS_PATH+"assets/js/substitutions/*.js", "!static_src/other/**/*.js"];
const JS_SUBSTITUTIONS_SRC = SUBSTITUTIONS_BUNDLE_FILES.map(f => ASSETS_PATH+"/assets/js/substitutions/" + f);
const SASS_SRC = ASSETS_PATH+"assets/**/*.scss";
const HTML_SRC = ["app/templates/*.html", "!app/templates/*.min.html"];

const SOURCEMAP_SOURCE_ROOT = "../../static_src";


// ================
// CACHE-BUSTING
// ================

const buster = require("gulp-buster");

gulp.task("cache-busting",() => {
    return gulp.src(["static/assets/**/*.js", "static/assets/**/*.css"])
        .pipe(buster({
            fileName: "cache_busting.json",
            relativePath: "static/"
        }))
        .pipe(gulp.dest("./app/templates"));
})


// ================
// BUILD-JS
// ================

const uglify = require("gulp-uglify");
const wrap = require("gulp-wrap");
const concat = require("gulp-concat");


function buildJS(src, dest=DEST) {
    return src
        .pipe(wrap('!function(){"use strict";<%= contents %>}()'))
        .pipe(uglify({
            toplevel: true
        }))
        .pipe(sourcemaps.write(".", {includeContent: false, sourceRoot: SOURCEMAP_SOURCE_ROOT}))
        .pipe(gulp.dest(dest));
}

gulp.task("build-js", () => {
    return buildJS(gulp.src(JS_SRC, {base: ASSETS_PATH})
        .pipe(sourcemaps.init()))
})

gulp.task("build-substitutions-js", () => {
    return buildJS(gulp.src(JS_SUBSTITUTIONS_SRC, {base: ASSETS_PATH})
        .pipe(sourcemaps.init())
        .pipe(concat("substitutions.js")), DEST+"assets/js/");
})


// ================
// BUILD-SASS
// ================

const sass = require("gulp-dart-sass");
const postcss = require("gulp-postcss");
const autoprefixer = require("autoprefixer");
const purgecss = require("@fullhuman/postcss-purgecss");
const replace = require("gulp-replace");

function getBootstrapIcon(name) {
    return fs.readFileSync("node_modules/bootstrap-icons/icons/" + name + ".svg", "utf8")
        .replace(/>\s*</g, "><")
        .replace(/"/g, "'");
}

gulp.task("build-sass", () => {
    return gulp.src(SASS_SRC, {base: ASSETS_PATH})
        .pipe(sourcemaps.init())
        .pipe(sass({
            outputStyle: "compressed"
        }))
        .pipe(postcss([
            purgecss({
                content: [
                    "app/templates/*.min.html",
                    "static/assets/*/*.js"
                ]
            }),
            autoprefixer()
        ]))
        .pipe(sourcemaps.write(".", {includeContent: false, sourceRoot: SOURCEMAP_SOURCE_ROOT}))
        .pipe(replace(/!bi-([\w-]*)/g, match => getBootstrapIcon(match.substr(4))))
        .pipe(gulp.dest(DEST));
})


// ================
// MINIFY-HTML
// ================

const htmlmin = require("gulp-html-minifier-terser");

gulp.task("minify-html", () => {
    return gulp.src(HTML_SRC)
        .pipe(replace(/<!--bi-([\w-]*)-->/g, (m, p1) => getBootstrapIcon(p1)))
        .pipe(htmlmin({
            collapseBooleanAttributes: true,
            collapseWhitespace: true,
            removeComments: true,
            ignoreCustomFragments: [/<!--bi-([\w-]*)-->/, /<\?(.*?)\?>/]
        }))
        .pipe(rename(p => p.extname=".min.html"))
        .pipe(gulp.dest("app/templates"));
});


// ================
// WATCHER
// ================

gulp.task("watch", () => {
    gulp.watch(JS_SRC, gulp.series(["build-js", "cache-busting"]));
    gulp.watch(JS_SUBSTITUTIONS_SRC, gulp.series(["build-substitutions-js", "cache-busting"]));
    gulp.watch(SASS_SRC, gulp.series(["build-sass", "cache-busting"]));
    gulp.watch(HTML_SRC, gulp.series(["minify-html"]));
});
