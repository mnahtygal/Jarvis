// Jarvis Monitor Overhang Camera Mount with Vertical Riser
// Designed for Logitech C920 overhead workbench camera
// OpenSCAD units are millimeters

$fn = 64;

// --------------------------------------------------
// UNIT CONVERSION
// --------------------------------------------------
inch = 25.4;


// --------------------------------------------------
// MAIN DIMENSIONS
// --------------------------------------------------

// Overall horizontal reach
total_len = 4.50 * inch;

// Width of the full mount
width = 1.50 * inch;


// --------------------------------------------------
// MONITOR CLIP
// --------------------------------------------------

clip_h   = 1.00 * inch;
clip_w   = 1.00 * inch;

// Thickness of the monitor where the clip fits
clip_gap = 0.68 * inch;


// --------------------------------------------------
// VERTICAL RISER
// --------------------------------------------------

// Change this value to test different heights
riser_h = 2.50 * inch;

// Thickness of riser front-to-back
riser_t = 0.40 * inch;


// --------------------------------------------------
// HORIZONTAL ARM
// --------------------------------------------------

arm_len = 3.50 * inch;
arm_t   = 0.35 * inch;


// --------------------------------------------------
// CAMERA END PAD
// --------------------------------------------------

end_h   = 0.50 * inch;
end_len = 0.90 * inch;


// --------------------------------------------------
// SHAPE SETTINGS
// --------------------------------------------------

fillet_r = 1.5;


// --------------------------------------------------
// HELPER: ROUNDED CUBE
// --------------------------------------------------

module rounded_cube(size=[10,10,10], r=1) {
    hull() {
        for (x = [r, size[0] - r])
        for (y = [r, size[1] - r])
        for (z = [r, size[2] - r])
            translate([x, y, z])
                sphere(r = r);
    }
}


// --------------------------------------------------
// MONITOR CLIP
// --------------------------------------------------

module monitor_clip() {
    difference() {

        rounded_cube(
            [clip_w, width, clip_h],
            r = fillet_r
        );

        // Opening that slides over monitor
        translate([
            (clip_w - clip_gap) / 2,
            -0.1,
            -0.1
        ])
        cube([
            clip_gap,
            width + 0.2,
            clip_h - (0.20 * inch)
        ]);
    }
}


// --------------------------------------------------
// VERTICAL RISER
// --------------------------------------------------

module riser() {

    // Main vertical support
    translate([
        clip_w - riser_t,
        0,
        clip_h - 0.05 * inch
    ])
    rounded_cube(
        [riser_t, width, riser_h],
        r = fillet_r
    );

    // Triangular reinforcement gusset
    translate([
        clip_w - riser_t,
        0,
        clip_h - 0.05 * inch
    ])
    linear_extrude(height = width)
        polygon(points = [
            [0, 0],
            [riser_t, 0],
            [riser_t, riser_h * 0.45]
        ]);
}


// --------------------------------------------------
// HORIZONTAL DIVING BOARD ARM
// --------------------------------------------------

module arm() {

    translate([
        clip_w - 0.05 * inch,
        0,
        clip_h + riser_h - arm_t
    ])
    rounded_cube(
        [arm_len, width, arm_t],
        r = fillet_r
    );
}


// --------------------------------------------------
// CAMERA PAD
// --------------------------------------------------

module camera_pad() {

    translate([
        clip_w + arm_len - end_len,
        0,
        clip_h + riser_h - end_h
    ])
    rounded_cube(
        [end_len, width, end_h],
        r = fillet_r
    );
}


// --------------------------------------------------
// COMPLETE MODEL
// --------------------------------------------------

union() {

    monitor_clip();

    riser();

    arm();

    camera_pad();
}