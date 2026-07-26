/*
===============================================================================
Project   : Jarvis Maker Lab
Component : Vision Tower V1
Part      : Base Mount
Version   : 1.0.0
Material  : ASA
Printer   : Bambu A1

Purpose:
  Printable base mount for a 60 x 60 mm Vision Tower column.
  Uses the validated 0.20 mm clearance per side from the ASA fit test.

Print orientation:
  Flat on the build plate exactly as modeled.

Supports:
  None required.
===============================================================================
*/

$fn = 64;

// -----------------------------------------------------------------------------
// User parameters
// -----------------------------------------------------------------------------
part = "base_mount";            // "base_mount" or "assembly_preview"

base_w = 120;
base_d = 120;
base_h = 10;
corner_r = 8;

column_w = 60;
column_d = 60;
fit_clearance = 0.20;           // clearance per side, validated in ASA

socket_wall = 6;
socket_h = 30;
socket_corner_r = 3;

mount_hole_d = 5.0;             // M4/M5-friendly clearance hole
mount_hole_edge = 14;
countersink_d = 9.5;
countersink_h = 2.4;

gusset_len = 22;
gusset_w = 8;
gusset_h = 20;

branding = true;
brand_text = "JARVIS";
brand_subtext = "VISION TOWER V1";
brand_depth = 0.7;

// -----------------------------------------------------------------------------
// Derived dimensions
// -----------------------------------------------------------------------------
socket_inner_w = column_w + 2 * fit_clearance;
socket_inner_d = column_d + 2 * fit_clearance;
socket_outer_w = socket_inner_w + 2 * socket_wall;
socket_outer_d = socket_inner_d + 2 * socket_wall;

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
module rounded_box(size=[10,10,10], r=2) {
    x = size[0];
    y = size[1];
    z = size[2];

    hull() {
        for (px = [r, x-r])
            for (py = [r, y-r])
                translate([px, py, 0])
                    cylinder(r=r, h=z);
    }
}

module base_plate() {
    difference() {
        rounded_box([base_w, base_d, base_h], corner_r);

        for (x = [mount_hole_edge, base_w-mount_hole_edge])
            for (y = [mount_hole_edge, base_d-mount_hole_edge]) {
                // Through hole
                translate([x, y, -0.1])
                    cylinder(d=mount_hole_d, h=base_h+0.2);

                // Top countersink / screw-head recess
                translate([x, y, base_h-countersink_h])
                    cylinder(d1=mount_hole_d, d2=countersink_d,
                             h=countersink_h+0.1);
            }
    }
}

module socket_body() {
    translate([
        (base_w-socket_outer_w)/2,
        (base_d-socket_outer_d)/2,
        base_h
    ])
    difference() {
        rounded_box([socket_outer_w, socket_outer_d, socket_h], socket_corner_r);

        // Column receiver. It starts slightly below the socket so the bottom is
        // cleanly opened while retaining the full base plate as a floor.
        translate([socket_wall, socket_wall, -0.1])
            cube([socket_inner_w, socket_inner_d, socket_h+0.2]);
    }
}

module triangular_gusset(length=20, width=8, height=20) {
    rotate([90,0,0])
        linear_extrude(height=width)
            polygon(points=[[0,0],[length,0],[0,height]]);
}

module gussets() {
    cx = base_w/2;
    cy = base_d/2;
    half_x = socket_outer_w/2;
    half_y = socket_outer_d/2;

    // Front and rear gussets
    translate([cx-gusset_w/2, cy-half_y, base_h])
        rotate([0,0,90]) triangular_gusset(gusset_len, gusset_w, gusset_h);

    translate([cx+gusset_w/2, cy+half_y, base_h])
        rotate([0,0,-90]) triangular_gusset(gusset_len, gusset_w, gusset_h);

    // Left and right gussets
    translate([cx-half_x, cy+gusset_w/2, base_h])
        triangular_gusset(gusset_len, gusset_w, gusset_h);

    translate([cx+half_x, cy-gusset_w/2, base_h])
        rotate([0,0,180]) triangular_gusset(gusset_len, gusset_w, gusset_h);
}

module branding_marks() {
    if (branding) {
        // Shallow recessed lettering on the top surface, outside the socket.
        translate([base_w/2, 15, base_h-brand_depth+0.01])
            linear_extrude(height=brand_depth)
                text(brand_text, size=9, halign="center", valign="center",
                     font="Liberation Sans:style=Bold");

        translate([base_w/2, base_d-13, base_h-brand_depth+0.01])
            linear_extrude(height=brand_depth)
                text(brand_subtext, size=4.5, halign="center", valign="center",
                     font="Liberation Sans:style=Bold");
    }
}

module base_mount() {
    difference() {
        union() {
            base_plate();
            socket_body();
            gussets();
        }
        branding_marks();
    }
}

module assembly_preview() {
    color("dimgray") base_mount();

    // Preview-only tower column. Do not export this mode for the base STL.
    color([0.85,0.85,0.85,0.65])
        translate([
            (base_w-column_w)/2,
            (base_d-column_d)/2,
            base_h+0.2
        ])
        difference() {
            cube([column_w, column_d, 140]);
            translate([3,3,-0.1])
                cube([column_w-6, column_d-6, 140.2]);
        }
}

// -----------------------------------------------------------------------------
// Render selection
// -----------------------------------------------------------------------------
if (part == "assembly_preview")
    assembly_preview();
else
    base_mount();
