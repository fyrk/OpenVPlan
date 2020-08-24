const gulp = require("gulp");
const argv = require("yargs").argv;
const sourcemaps = require("gulp-sourcemaps");
const rename = require("gulp-rename");


const closureCompiler = require("google-closure-compiler").gulp();

gulp.task("build-js", () => {
    const srcPath = argv.src;
    const outputFile = argv.output_file;
    const destPath = argv.dest;
    return gulp.src(srcPath, {base: './'})
        .pipe(sourcemaps.init())
        .pipe(closureCompiler({
            js_output_file: outputFile,
            assume_function_wrapper: true,
            source_map_format: "V3",
            language_in: "ECMASCRIPT_2019",
            language_out: "ECMASCRIPT_2019",
        }))
        .pipe(sourcemaps.write("/"))
        .pipe(gulp.dest(destPath));
})


const sass = require("gulp-sass");
const postcss = require("gulp-postcss");
const autoprefixer = require("autoprefixer");
const purgecss = require("postcss-purgecss");

gulp.task("build-sass", () => {
    const srcPath = argv.src;
    const destPath = argv.dest;
    const loadPath = argv.loadpath;
    return gulp.src(srcPath)
        .pipe(sourcemaps.init())
        .pipe(sass({
                outputStyle: "compressed",
                includePaths: [loadPath]
        }))
        .pipe(postcss([
            purgecss({
                content: [
                    "assets/templates/*.min.html",
                    "assets/static/assets/js/substitutions.min.js"
                ],
                whitelist: [
                    "view-email"  // about.scss
                ],
                css: [srcPath]
            }),
            autoprefixer()
        ]))
        .pipe(sourcemaps.write("/"))
        .pipe(gulp.dest(destPath));
});


const htmlmin = require("gulp-html-minifier");

gulp.task("build-html", () => {
    const srcPath = argv.src;
    const destPath = argv.dest;
    const destName = argv.dest_name;
    return gulp.src(srcPath)
        .pipe(htmlmin({collapseWhitespace: true, conservativeCollapse: true, removeComments: true}))
        .pipe(rename(destName))
        .pipe(gulp.dest(destPath));
});
