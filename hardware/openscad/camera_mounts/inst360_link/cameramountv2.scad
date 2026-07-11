// Monitor Overhang Camera Mount
// Side-view model based on sketch
// Units: inches

$fn = 64;

// ---------- Dimensions ----------
total_len = 4.50;
width     = 1.50;

clip_h    = 1.00;
clip_w    = 1.00;
clip_gap  = 0.68;

arm_len   = 3.50;
arm_t     = 0.25;

end_h     = 1.00;
end_len   = 0.75;

fillet_r  = 0.06;


// ---------- Helpers ----------
module rounded_cube(size=[1,1,1], r=0.05) {
    hull() {
        for (x=[r, size[0]-r])
        for (y=[r, size[1]-r])
        for (z=[r, size[2]-r])
            translate([x,y,z])
                sphere(r=r);
    }
}


// ---------- Model ----------
union() {

    // Left monitor clip / upside-down U
    difference() {
        rounded_cube([clip_w, width, clip_h], r=fillet_r);

        // monitor slot
        translate([(clip_w - clip_gap) / 2, -0.01, -0.01])
            cube([clip_gap, width + 0.02, clip_h - 0.20]);
    }

    // Diving-board arm
    translate([clip_w - 0.05, 0, clip_h - arm_t])
        rounded_cube([arm_len, width, arm_t], r=fillet_r);

    // Thicker camera pad at the far end
    translate([clip_w + arm_len - end_len, 0, 0])
        rounded_cube([end_len, width, end_h], r=fillet_r);
}