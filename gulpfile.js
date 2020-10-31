const gulp = require("gulp");
const argv = require("yargs").argv;
const sourcemaps = require("gulp-sourcemaps");
const rename = require("gulp-rename");


const closureCompiler = require("google-closure-compiler").gulp();

const SUBSTITUTIONS_BUNDLE_FILES = [
    "substitutions-base.js",
    "grey-substitutions.js",
    "push-notifications.js",
    "updates.js"
];

gulp.task("build-js", () => {
    const srcFile = argv.srcFile;
    let destFile = argv.destFile;
    const path = argv.path || "assets/static/assets/js/";
    let s;
    if (SUBSTITUTIONS_BUNDLE_FILES.includes(srcFile)) {
        let paths = [];
        for (let filename of SUBSTITUTIONS_BUNDLE_FILES) paths.push(path + filename);
        s = gulp.src(paths);
        destFile = "substitutions.min.js";
    } else {
        s = gulp.src(path + srcFile);
    }
    return s
        .pipe(sourcemaps.init())
        .pipe(closureCompiler({
            js_output_file: destFile,
            assume_function_wrapper: true,
            isolation_mode: "IIFE",
            source_map_format: "V3",
            language_in: "ECMASCRIPT_2019",
            language_out: "ECMASCRIPT_2019",
        }))
        .pipe(sourcemaps.write("/"))
        .pipe(gulp.dest(path));
})


const sass = require("gulp-sass");
const postcss = require("gulp-postcss");
const autoprefixer = require("autoprefixer");
const purgecss = require("postcss-purgecss");

gulp.task("build-sass", () => {
    const srcFile = argv.srcFile;
    const path = argv.path || "assets/static/assets/style/";
    return gulp.src(path + srcFile)
        .pipe(sourcemaps.init())
        .pipe(sass({
            outputStyle: "compressed",
            outFile: path
        }))
        .pipe(postcss([
            purgecss({
                content: [
                    "assets/templates/*.min.html",
                    "assets/static/assets/js/substitutions.min.js"
                ],
                css: [path + srcFile]
            }),
            autoprefixer()
        ]))
        .pipe(sourcemaps.write("/"))
        .pipe(gulp.dest(path));
});


const htmlmin = require("gulp-html-minifier");

gulp.task("minify-xml", () => {
    const srcFile = argv.srcFile;
    const destFile = argv.destFile;
    const path = argv.path || "assets/templates/";
    return gulp.src(path + srcFile)
        .pipe(htmlmin({collapseWhitespace: true, conservativeCollapse: true, removeComments: true}))
        .pipe(rename(destFile))
        .pipe(gulp.dest(path));
});
