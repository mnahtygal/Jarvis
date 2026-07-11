// Adjustable Monitor Mount Arm for Insta360
// Designed for custom adjustment and rigid locking.

// --- Parameters ---
arm_length = 80;        // mm
arm_width = 20;         // mm
arm_thickness = 10;     // mm
joint_radius = 15;      // mm
mount_hole_dia = 5;     // mm (for bolt)

// --- Modules ---

module arm_segment() {
    union() {
        // Main body
        cube([arm_length, arm_width, arm_thickness], center=true);
        
        // Pivot joint end
        translate([arm_length/2, 0, 0])
            cylinder(r=joint_radius, h=arm_thickness, center=true);
    }
}

module main_assembly() {
    // Arm 1 (Base to Elbow)
    arm_segment();
    
    // Elbow joint
    translate([arm_length/2, 0, 0])
        rotate([0, 0, 45]) // Adjustable angle
        translate([arm_length/2, 0, 0])
            arm_segment();
}

// --- Execution ---
// Assumptions: Requires M5 bolt and wingnut for friction locking.
// The joint uses a through-hole for variable tightening.
difference() {
    main_assembly();
    
    // Joint mounting holes
    translate([arm_length/2, 0, 0])
        cylinder(d=mount_hole_dia, h=arm_thickness*2, center=true);
}