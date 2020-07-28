const gulp = require("gulp");
const argv = require("yargs").argv;
const sourcemaps = require("gulp-sourcemaps");
const sass = require("gulp-sass");
const purgecss = require("gulp-purgecss");
const closureCompiler = require("google-closure-compiler").gulp();

gulp.task("js", () => {
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

gulp.task("sass", () => {
    const srcPath = argv.src;
    const destPath = argv.dest;
    const loadPath = argv.loadpath;
    return gulp.src(srcPath)
        .pipe(sourcemaps.init())
        .pipe(sass({
                outputStyle: "compressed",
                includePaths: [loadPath]
        }))
        .pipe(purgecss({
            content: [
                "assets/templates/*.min.html",
                "assets/static/assets/js/substitutions.min.js"
            ],
            css: [srcPath],
        }))
        .pipe(sourcemaps.write("/"))
        .pipe(gulp.dest(destPath));
});
